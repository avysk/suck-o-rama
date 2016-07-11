"""
Python 3 / Tkinter gopher client
"""

import logging
import socket
import tkinter as tk
from tkinter import font, ttk

from collections import namedtuple

# Constants affecting rendering

PLAIN_TEXT_PADDING = ' ' * 4
VERSION = '-=[ Suck-O-Rama 0.3 ]=-        '


def char_to_info(kind):
    """
    How to represent entry in gopher directory in control column.
    """
    return {'i': "        ",
            '0': "TEXT    ",
            '1': " DIR    "}.get(kind, "?[{}]    ".format(kind))

# Icons
HOME = \
        'R0lGODlhEAAQAPAAAAAAAAAAACH5BAEAAAEALAAAAAAQABAA'\
        'AAImjB8AyKja2HsxzSuvProv401OCHHkB55jmbKWK5owJaOvXeX6UQAAOw=='
BACK = \
        'R0lGODlhEAAQAPAAAAAAAAAAACH5BAEAAAEALAAAAAAQABAA'\
        'AAIkjA2px6G/GJzgTHdxpDpZ+jQNJI5h+Z0oh3Bkt5EsPLfg+h4FADs='
RELOAD = \
        'R0lGODlhEAAQAPAAAAAAAAAAACH5BAEAAAEALAAAAAAQABAA'\
        'AAImjA2px6G/EloHAifblFnbznyXRoJkNZ5hqm7t+qJs+6wzJp5WUwAAOw=='


def get_data(host, port, selector, callback):
    """
    Download data from the given selector and call callback with it.
    """
    sock = socket.socket()
    sock.connect((host, port))
    sock.send(selector.encode() + b'\r\n')
    data = b''
    while True:
        more = sock.recv(1024)
        if not more:
            break
        data += more
    lines = data.decode().split('\r\n')
    if lines[-1] == '':
        del lines[-1]
    callback(lines)

State = namedtuple('State',
                   ['kind', 'host', 'port', 'selector', 'data', 'c_index'])


# pylint: disable=too-many-instance-attributes
class Interface():
    """
    User interface.
    """
    def __init__(self, app):
        self._app = app

        # Root
        self._root = tk.Tk()
        self._root.title(VERSION)
        self._root.bind('<Up>', self._sel_up)
        self._root.bind('<Down>', self._sel_down)
        self._root.bind('<Right>', app.jump)
        self._root.bind('<Left>', app.back)

        # Buttons
        self._icons = {}
        self._load_icons()

        self._frame = tk.Frame(self._root)
        self._frame.grid(row=0, column=1, sticky=tk.N+tk.S+tk.W+tk.E)

        for kind, cmd in [
                ['HOME', app.cmd_home],
                ['BACK', app.cmd_back],
                ['RELOAD', app.cmd_reload]]:
            self._add_button(kind, cmd)

        # Address line
        self._addr_string = tk.StringVar(self._root, name='addr')
        ttk.Label(self._root, textvariable='addr').grid(
            row=1, column=1, sticky=tk.N+tk.S+tk.E)
        self.addr = ''

        # Main text widget and scrollbar
        fnt = font.Font(family='Cousine', size=12)
        self._text = tk.Text(self._root, width=80, height=35, font=fnt)
        scroll = ttk.Scrollbar(self._root, command=self._text.yview)
        scroll.grid(row=2, column=0, sticky=tk.N+tk.S+tk.W+tk.E)
        self._text.configure(yscrollcommand=scroll.set,
                             background='white', foreground='black')
        self._text.grid(row=2, column=1, sticky=tk.N+tk.S+tk.W+tk.E)
        # We do not need bulit-in mouse event with selection etc.
        # TO DO: actually, we may want selection.
        self._text.bind('<1>', lambda event: 'break')
        self._text.bind('<B1-Motion>', lambda event: 'break')
        self._text.focus()
        self._text['state'] = 'disabled'

        # Tags
        self._tags = ['active_link', 'dir', 'error', 'item', 'unknown']
        for tag in self._tags:
            self._text.tag_add(tag, '0.0', '0.0')
        self._text.tag_configure('error', foreground='red')
        self._text.tag_configure('dir', foreground='blue')
        self._text.tag_configure('item', foreground='green')
        self._text.tag_bind('dir', '<1>', self._select_entry)
        self._text.tag_bind('item', '<1>', self._select_entry)
        self._text.tag_bind('dir', '<Double-Button-1>', self._app.jump)
        self._text.tag_bind('item', '<Double-Button-1>', self._app.jump)

        # Status line
        self._label_status = tk.StringVar(self._root, name='status')
        ttk.Label(self._root, textvariable='status').grid(
            row=3, column=1, sticky=tk.N+tk.S+tk.W+tk.E)
        self.status = ''

        # Resize only text area
        self._root.columnconfigure(2, weight=1)
        self._root.rowconfigure(2, weight=1)

        # Indices of 'link' lines
        self._link_indices = []

    @property
    def status(self):
        """
        Get status string.
        """
        txt = self._label_status.get()[len(VERSION):]
        if txt.startswith(' '):
            txt = txt[1:]
        return txt

    @status.setter
    def status(self, val):
        """
        Set status string.
        """
        txt = VERSION
        if len(val) > 0:
            txt += ' ' + val
        self._label_status.set(txt)

    @property
    def addr(self):
        """
        Get address string.
        """
        return self._addr_string.get()

    @addr.setter
    def addr(self, val):
        """
        Set address string.
        """
        self._addr_string.set(val)

    def _load_icons(self):
        self._icons['HOME'] = tk.PhotoImage(data=HOME)
        self._icons['BACK'] = tk.PhotoImage(data=BACK)
        self._icons['RELOAD'] = tk.PhotoImage(data=RELOAD)

    def _add_button(self, kind, cmd):
        btn = ttk.Button(self._frame, image=self._icons[kind],
                         command=cmd, takefocus=False)
        btn.pack(side=tk.LEFT)

    # Methods to bind keys

    def _sel_up(self, event):
        logging.debug('_sel_up: %s', str(event))
        self._update_sel(-1)

    def _sel_down(self, event):
        logging.debug('_sel_down: %s', str(event))
        self._update_sel(1)

    def _update_sel(self, delta):
        total = len(self._link_indices)
        if total:
            self._app.cind += delta
            self._app.cind %= total
            self.update_control()

    # Methods to bind tags

    def _select_entry(self, event):
        coord = self._text.index('@{},{}'.format(event.x, event.y))
        self._app.cind = self._link_indices.index(coord.split('.')[0] + '.0')
        self.update_control()
        return 'break'

    # Public interface

    def update_control(self):
        """
        Mark active link according to self._app.cind.
        """
        self._text['state'] = 'normal'
        start = self._link_indices[self._app.cind]
        self._text.see(start)
        end = start + ' + 6c'
        self._text.tag_remove('active_link', '0.0', 'end')
        self._text.tag_add('active_link', start, end)
        self._text.tag_configure('active_link', background='yellow')
        self._text['state'] = 'disable'

    def clear_all(self):
        """
        Clear text widget and other stuff.
        """
        self.status = ''
        self.addr = ''
        self._link_indices = []
        self._text['state'] = 'normal'
        for tag in self._tags:
            self._text.tag_remove(tag, '0.0', 'end')
        self._text.delete('0.0', 'end')
        self._text.update()
        self._text['state'] = 'disabled'

    def enable_updates(self):
        """
        Allow updates to text.
        """
        self._text['state'] = 'normal'

    def disable_updates(self):
        """
        Disallow updates to text.
        """
        self._text['state'] = 'disabled'

    def insert_with_tag(self, txt, idx1, idx2, tag):
        """
        Insert given text and apply given tag between indices.
        """
        self._text.insert('end', txt)
        self._text.tag_add(tag, idx1, idx2)

    def insert(self, txt):
        """
        Insert given text.
        """
        self._text.insert('end', txt)

    def insert_with_padding(self, txt_list):
        """
        Insert lines from given list, with padding.
        """
        for line in txt_list:
            self._text.insert('end', PLAIN_TEXT_PADDING + line + '\n')

    def add_link_idx(self):
        """
        Store the index of the last added line.
        """
        self._link_indices.append(self._text.index('end-2l'))


class SuckORama():
    """
    Main application.
    """
    def __init__(self):
        self._ui = Interface(self)
        # Init chosen item
        self._c_lines = []
        # Init history
        self._history = []
        # Init state
        self._state = None

    def run(self, host, port, selector):
        """
        Start the application, using given selector as home.
        """
        self._state = State(host=host, port=port, selector=selector,
                            kind='1', data=[], c_index=[])
        self._render_from_network()
        tk.mainloop()

    # Main operations

    def jump(self, event):
        """
        Go to next page according to chosen control.
        """
        logging.debug('_go: %s', str(event))
        if not self._c_lines:
            return
        cline = self._c_lines[self.cind]
        fields = cline.split('\t')
        # TO DO
        kind = fields[0][0]
        selector = fields[1]
        host = fields[2]
        port = int(fields[3])
        self._history.append(self._state)
        self._state = State(kind=kind, host=host, port=port,
                            selector=selector, data=[], c_index=[0])
        self._render_from_network()
        return 'break'

    def _render_from_network(self):
        kind = self._state.kind
        host = self._state.host
        port = self._state.port
        selector = self._state.selector
        self.cind = 0
        callback = self._update(kind)
        get_data(host, port, selector, callback)

    def _update(self, kind):
        renderer = self._kind_to_render(kind)

        def _callback(lines, renderer=renderer):
            self._state.data[:] = []
            self._state.data.extend(lines)
            renderer()
        return _callback

    def back(self, event):
        """
        Go to the previous page in history.
        """
        logging.debug('_back: %s', str(event))
        if len(self._history) == 0:
            return
        self._state = self._history.pop()
        renderer = self._kind_to_render(self._state.kind)
        renderer()

    # Helpers

    def _kind_to_render(self, kind):
        return {'0': self._render_text,
                '1': self._render_dir}[kind]

    @property
    def cind(self):
        """
        Get index of selected link.
        """
        idx = self._state.c_index
        return idx and idx[0]

    @cind.setter
    def cind(self, new):
        """
        Set the index of selected link.
        """
        idx = self._state.c_index
        if idx:
            idx[0] = new
        else:
            idx.append(new)

    def _render_text(self):
        """
        Render kind '0' documents (= plain text).
        """
        self._sanitize_data()
        self._c_lines = []
        self._ui.clear_all()
        self._ui.addr = 'TEXT: {}:{}{}'.format(self._state.host,
                                               self._state.port,
                                               self._state.selector)
        logging.debug(self._state.data)
        got_lastline = False
        # Check for error message
        if len(self._state.data) > 0:
            maybe = self._state.data[0]
            if maybe.startswith('3'):
                fields = maybe.split('\t')
                if len(fields) >= 4:
                    error = fields[0][1:]
                self._ui.enable_updates()
                self._ui.insert_with_tag('[SERVER ERROR] ',
                                         '0.0', 'end-1c', 'error')
                self._ui.insert(error + '\n')
                if len(self._state.data) > 1:
                    self._ui.status += '[TRAILING DATA OMITTED]'
                self._ui.disable_updates()
                return
        to_render = []
        for line in self._state.data:
            if got_lastline:
                self._ui.status += '[TRAILING DATA OMITTED]'
                break
            if line == '.':
                got_lastline = True
                continue
            else:
                # since '.' is Lastline, single dot must be doubled; client has
                # to strip it back
                if line == '..':
                    line = '.'
                to_render.append(line)
        if not got_lastline:
            self._ui.status += '[POSSIBLY INCOMPLETE]'
        self._ui.enable_updates()
        self._ui.insert_with_padding(to_render)
        self._ui.disable_updates()

    def _sanitize_data(self):
        """
        Split text into lines by '\n'.
        """
        lines = []
        for line in self._state.data:
            lines.extend(line.split('\n'))
        self._state.data[:] = lines

    def _render_dir(self):
        """
        Render kind '1' documents (= gopher directory).
        """
        self._c_lines = []
        self._ui.clear_all()
        self._ui.addr = 'DIR: {}:{}{}'.format(self._state.host,
                                              self._state.port,
                                              self._state.selector)
        # FIXME
        # Maybe we got bad server, which sends us the data separated by
        # '\n' and not by '\r\n'
        self._sanitize_data()
        logging.debug(self._state.data)
        got_end = False
        trailing = False
        self._ui.enable_updates()
        for line in self._state.data:
            if got_end:
                self._ui.status += '[TRAILING DATA OMITTED]'
                got_end = False
                trailing = True
            if line == '.':
                got_end = True
                continue
            if line == '':
                # TO DO shouldn't we produce '\n'?
                continue

            kind = line[0]
            tag = {'1': 'dir', '0': 'item'}.get(kind, 'unknown')

            try:
                tab = line.index('\t')
            except ValueError:
                tab = None
            out = char_to_info(kind)
            if tab:
                out += line[1:tab]
            else:
                out += line[1:]
            out += '\n'
            self._ui.insert_with_tag(out, 'end-2l', 'end-2c', tag)
            if kind in {'0', '1'}:
                self._ui.add_link_idx()
                self._c_lines.append(line)
        if not trailing and not got_end:
            self._ui.status += '[POSSIBLY INCOMPLETE]'
        self._ui.disable_updates()
        if self._c_lines:
            if not self.cind:
                self.cind = 0
            self._ui.update_control()

    # Button commands

    def cmd_home(self):
        """
        Return to the start page.
        """
        if self._history:
            del self._history[1:]
            self.back("whatever")
        self.cind = 0
        self._ui.update_control()

    def cmd_back(self):
        """
        Go back to previous page.
        """
        self.back("whatever")

    def cmd_reload(self):
        """
        Reload current page.
        """
        self._render_from_network()

if __name__ == '__main__':
    SuckORama().run('legume.ocaml.nl', 70, '')
