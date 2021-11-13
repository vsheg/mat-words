from argparse import ArgumentParser
from typing import Optional

from tqdm import tqdm

from src.etl import get_all_comments, get_all_posts, get_id_by_name

from . import log


def cli():

    parser = ArgumentParser()
    parser.add_argument('ids', nargs='+', type=str, help='Page IDs or names.')
    parser.add_argument(
        '--comments', '-c', type=bool, default=True, help='Download comments.'
    )
    parser.add_argument(
        '--limit', '-l', type=int, default=None, help='Latest posts number limit.'
    )
    parser.add_argument(
        '--offset',
        '-o',
        type=int,
        default=0,
        help='Number of latest posts to be ignored.',
    )

    args = parser.parse_args()

    for page_id in tqdm(args.ids, desc='IDs'):

        try:
            try:
                page_id = int(page_id)
            except:
                if _page_id := get_id_by_name(page_id):
                    page_id = -_page_id
                else:
                    log.error(
                        'Could\'t find ID for `{page_id}`',
                    )
                    continue

            post_ids = get_all_posts(owner_id=page_id, limit=args.limit)
            if args.comments:
                get_all_comments(owner_id=page_id, post_ids=post_ids)
        except Exception as e:
            log.error(
                'Could not retrieve everything for the page `{}`',
                page_id,
                extra={'exception': e},
            )


if __name__ == '__main__':
    cli()
