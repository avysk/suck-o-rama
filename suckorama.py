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
VERSION = '-=[ Suck-O-Rama 0.1 ]=-        '


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


# pylint: disable=too-few-public-methods,too-many-instance-attributes
class SuckORama():
    """
    Main application.
    """
    def __init__(self):
        # Init GUI
        self._root = tk.Tk()
        self._root.title("Suck-O-Rama")
        self._root.bind('<Up>', self._sel_up)
        self._root.bind('<Down>', self._sel_down)
        self._root.bind('<Right>', self._go)
        self._root.bind('<Left>', self._back)

        self._icons = {}
        self._load_icons()

        self._frame = tk.Frame(self._root)
        self._frame.grid(row=0, column=1, sticky=tk.N+tk.S+tk.W+tk.E)

        for kind, cmd in [
                ['HOME', self._cmd_home],
                ['BACK', self._cmd_back],
                ['RELOAD', self._cmd_reload]]:
            self._add_button(kind, cmd)

        fnt = font.Font(family='Cousine', size=12)
        self._text = tk.Text(self._root, width=80, height=35, font=fnt)
        scroll = ttk.Scrollbar(self._root, command=self._text.yview)
        scroll.grid(row=2, column=0, sticky=tk.N+tk.S+tk.W+tk.E)

        self._addr_string = tk.StringVar(self._root, name='addr')
        ttk.Label(self._root, textvariable='addr').grid(
            row=1, column=1, sticky=tk.N+tk.S+tk.E)
        self._addr = ''

        self._text.configure(yscrollcommand=scroll.set,
                             background='white', foreground='black')
        self._text.grid(row=2, column=1, sticky=tk.N+tk.S+tk.W+tk.E)

        self._root.columnconfigure(2, weight=1)
        self._root.rowconfigure(2, weight=1)

        self._text.bind('<1>', lambda event: 'break')
        self._text.bind('<B1-Motion>', lambda event: 'break')
        self._text.focus()
        self._text['state'] = 'disabled'

        self._label_status = tk.StringVar(self._root, name='status')
        ttk.Label(self._root, textvariable='status').grid(
            row=3, column=1, sticky=tk.N+tk.S+tk.W+tk.E)
        self._status = ''

        # Init chosen item
        self._controls = []
        self._c_lines = []

        # Init history
        self._history = []

        # Init state
        self._state = None

    @property
    def _status(self):
        txt = self._label_status.get()[len(VERSION):]
        if txt.startswith(' '):
            txt = txt[1:]
        return txt

    @_status.setter
    def _status(self, val):
        txt = VERSION
        if len(val) > 0:
            txt += ' ' + val
        self._label_status.set(txt)

    @property
    def _addr(self):
        return self._addr_string.get()

    @_addr.setter
    def _addr(self, val):
        self._addr_string.set(val)

    # Misc init-GUI stuff

    def _load_icons(self):
        self._icons['HOME'] = tk.PhotoImage(data=HOME)
        self._icons['BACK'] = tk.PhotoImage(data=BACK)
        self._icons['RELOAD'] = tk.PhotoImage(data=RELOAD)

    def _add_button(self, kind, cmd):
        btn = ttk.Button(self._frame, image=self._icons[kind],
                         command=cmd, takefocus=False)
        btn.pack(side=tk.LEFT)

    # Entry point

    def run(self, host, port, selector):
        """
        Start the application, using given selector as home.
        """
        self._state = State(host=host, port=port, selector=selector,
                            kind='1', data=[], c_index=[])
        self._render_from_network()
        tk.mainloop()

    # Main operations

    def _go(self, event):
        """
        Go to next page according to chosen control.
        """
        logging.debug('_go: %s', str(event))
        if not self._c_lines:
            return
        cline = self._c_lines[self._state.c_index[0]]
        fields = cline.split('\t')
        # XXX
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
        self._cind = 0
        callback = self._update(kind)
        get_data(host, port, selector, callback)

    def _update(self, kind):
        renderer = self._kind_to_render(kind)

        def _callback(lines, renderer=renderer):
            self._state.data[:] = []
            self._state.data.extend(lines)
            renderer()
        return _callback

    def _back(self, event):
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
    def _cind(self):
        idx = self._state.c_index
        return idx and idx[0]

    @_cind.setter
    def _cind(self, new):
        idx = self._state.c_index
        if idx:
            idx[0] = new
        else:
            idx.append(new)

    def _select_entry(self, event):
        coord = self._text.index('@{},{}'.format(event.x, event.y))
        self._cind = self._controls.index(coord.split('.')[0] + '.0')
        self._update_control()
        return 'break'

    # GUI methods

    def _clear_all(self):
        """
        Clear text widget and other stuff.
        """
        self._status = ''
        self._addr = ''
        self._text['state'] = 'normal'
        for tag in ['choose', 'dir', 'error', 'item']:
            self._text.tag_remove(tag, '0.0', 'end')
        self._text.delete('0.0', 'end')
        self._text.update()
        self._text['state'] = 'disabled'

    def _sel_up(self, event):
        logging.debug('_sel_up: %s', str(event))
        self._update_sel(-1)

    def _sel_down(self, event):
        logging.debug('_sel_down: %s', str(event))
        self._update_sel(1)

    def _update_sel(self, delta):
        total = len(self._c_lines)
        if total:
            self._cind += delta
            self._cind %= total
            self._update_control()

    # Renderers

    def _render_text(self):
        """
        Render kind '0' documents (= plain text).
        """
        self._sanitize_text()
        self._c_lines = []
        self._controls = []
        self._clear_all()
        self._addr = 'TEXT: {}:{}{}'.format(self._state.host,
                                            self._state.port,
                                            self._state.selector)
        self._text['state'] = 'normal'
        logging.debug(self._state.data)
        got_lastline = False
        # Check for error message
        if len(self._state.data) > 0:
            maybe = self._state.data[0]
            if maybe.startswith('3'):
                fields = maybe.split('\t')
                if len(fields) >= 4:
                    error = fields[0][1:]
                self._text.insert('end', '[SERVER ERROR] ')
                self._text.tag_add('error', '0.0', 'end -1c')
                self._text.tag_configure('error', foreground='red')
                self._text.insert('end', error + '\n')
                if len(self._state.data) > 1:
                    self._status += '[TRAILING DATA OMITTED]'
                self._text['state'] = 'disabled'
                return
        for line in self._state.data:
            if got_lastline:
                self._status += '[TRAILING DATA OMITTED]'
                break
            if line == '.':
                got_lastline = True
                continue
            else:
                # since '.' is Lastline, single dot must be doubled; client has
                # to strip it back
                if line == '..':
                    line = '.'
                self._text.insert('end', PLAIN_TEXT_PADDING + line + '\n')
        if not got_lastline:
            self._status += '[POSSIBLY INCOMPLETE]'
        self._text['state'] = 'disabled'

    def _sanitize_text(self):
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
        self._controls = []
        self._clear_all()
        self._addr = 'DIR: {}:{}{}'.format(self._state.host,
                                           self._state.port,
                                           self._state.selector)
        # FIXME
        # Maybe we got bad server, which sends us the data separated by
        # '\n' and not by '\r\n'
        self._sanitize_text()
        self._text['state'] = 'normal'
        logging.debug(self._state.data)
        got_end = False
        trailing = False
        for line in self._state.data:
            if got_end:
                self._status += '[TRAILING DATA OMITTED]'
                got_end = False
                trailing = True
            if line == '.':
                got_end = True
                continue
            if line == '':
                continue
            try:
                tab = line.index('\t')
            except ValueError:
                tab = None
            if tab:
                self._text.insert('end', char_to_info(line[0]) + line[1:tab])
            else:
                self._text.insert('end', char_to_info(line[0]) + line[1:])
            self._text.insert('end', '\n')
            if line[0] == '1':
                self._text.tag_add('dir', 'end -2 lines', 'end -2c')
                self._controls.append(self._text.index('end - 2 lines'))
                self._c_lines.append(line)
            elif line[0] == '0':
                self._text.tag_add('item', 'end -2 lines', 'end -2c')
                self._controls.append(self._text.index('end - 2 lines'))
                self._c_lines.append(line)
        if not trailing and not got_end:
            self._status += '[POSSIBLY INCOMPLETE]'
        self._text.tag_configure('dir', foreground='blue')
        self._text.tag_configure('item', foreground='green')
        self._text.tag_bind('dir', '<1>', self._select_entry)
        self._text.tag_bind('item', '<1>', self._select_entry)
        self._text.tag_bind('dir', '<Double-Button-1>', self._go)
        self._text.tag_bind('item', '<Double-Button-1>', self._go)
        self._text['state'] = 'disabled'
        if self._controls:
            if not self._cind:
                self._cind = 0
            self._update_control()

    def _update_control(self):
        self._text['state'] = 'normal'
        start = self._controls[self._cind]
        self._text.see(start)
        end = start + ' + 6c'
        self._text.tag_remove('choose', '0.0', 'end')
        self._text.tag_add('choose', start, end)
        self._text.tag_configure('choose', background='yellow')
        self._text['state'] = 'disable'

    # Button commands

    def _cmd_home(self):
        if self._history:
            del self._history[1:]
            self._back("whatever")
        self._cind = 0
        self._update_control()

    def _cmd_back(self):
        self._back("whatever")

    def _cmd_reload(self):
        self._render_from_network()

if __name__ == '__main__':
    SuckORama().run('legume.ocaml.nl', 70, '')
