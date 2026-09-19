"""python -m chamber [serve|deck-add|backup]"""
import argparse
import sqlite3
import webbrowser

from . import core, db
from .server import make_server


def main():
    p = argparse.ArgumentParser(prog='chamber', description='Dragapult Time Chamber')
    p.add_argument('--db', default=None, help=f'SQLite file (default {db.default_path()}, or $CHAMBER_DB)')
    sub = p.add_subparsers(dest='cmd')
    s = sub.add_parser('serve', help='run the local app (default)')
    s.add_argument('--host', default='127.0.0.1')
    s.add_argument('--port', type=int, default=8765)
    s.add_argument('--no-open', action='store_true')
    d = sub.add_parser('deck-add', help='store a new immutable deck version from a PTCGL export file')
    d.add_argument('file')
    d.add_argument('--source', required=True, help='where this exact list comes from')
    d.add_argument('--deck', default='dragapult')
    d.add_argument('--format', default='')
    d.add_argument('--date', default='')
    b = sub.add_parser('backup', help='consistent copy of the database')
    b.add_argument('dest')
    a = p.parse_args()
    path = a.db or db.default_path()

    if a.cmd == 'deck-add':
        conn = db.connect(path)
        core.load_seed(conn)
        cards = core.parse_deck(open(a.file, encoding='utf-8').read())
        h = core.add_deck(conn, a.deck, cards, a.source, a.format, a.date)
        print(f'deck version: {core.deck_label(conn, h)}')
    elif a.cmd == 'backup':
        src = db.connect(path)
        with sqlite3.connect(a.dest) as dst:
            src.backup(dst)
        print(f'backed up {path} -> {a.dest}')
    else:
        host, port, no_open = (a.host, a.port, a.no_open) if a.cmd == 'serve' else ('127.0.0.1', 8765, False)
        srv = make_server(path, host, port)
        url = f'http://{host}:{srv.server_address[1]}/'
        print(f'Dragapult Time Chamber on {url}  (data: {path})  Ctrl+C to stop')
        if not no_open:
            webbrowser.open(url)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
