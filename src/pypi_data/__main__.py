from __future__ import print_function
import argparse
import logging
import logging.config
import os.path
import sys

from pypi_data import FileSystemData

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', default=False, action='store_true')

    subparsers = parser.add_subparsers()
    
    init_parser = subparsers.add_parser('init')
    init_parser.set_defaults(handler=command_init)
    init_parser.add_argument('path')

    update_parser = subparsers.add_parser('update')
    update_parser.set_defaults(handler=command_update)
    update_parser.add_argument('path')

    full_download_parser = subparsers.add_parser('full-download')
    full_download_parser.set_defaults(handler=command_full_download)
    full_download_parser.add_argument('path')
    full_download_parser.add_argument('--confirm', dest='confirmed', default=False, action='store_true')
    
    args = parser.parse_args()

    log_level_name = 'DEBUG' if args.debug else 'INFO'

    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'console': {
                'format': '%(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'console',
                'level': log_level_name
            }
        },
        'loggers': {
            'pypi_data': {
                'handlers': ['console'],
                'level': log_level_name,
                'propagate': True
            }
        }
    })

    kwargs = vars(args)
    kwargs.pop('debug')
    kwargs.pop('handler')(FileSystemData(args.path), **kwargs)

def command_init(data, path):
    data.init()

def command_update(data, path):
    data.update()

def command_full_download(data, path, confirmed):
    if not confirmed:
        print((
            'WARNING: Will download ALL metadata.\n'
            '         This is time-consuming, and places a load on the PyPI servers.\n'
            '\n'
            'Alternatively, you can use `{program} init` to download a pregenerated\n'
            'archive.\n'
            '\n'
            'If you definitely want to download ALL metadata, type \'download\' below,\n'
            'or \'exit\' to abort.\n'
        ).format(program=os.path.basename(sys.argv[0])), file=sys.stderr)

        if raw_input('> ') != 'download':
            print('Aborting', file=sys.stderr)
            return

    data.full_download()

if __name__ == '__main__':
    main()
