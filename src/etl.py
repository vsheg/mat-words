from datetime import datetime
from time import sleep, time
from typing import Iterable, Mapping, Optional

from httpx import Client
from loguru import logger as log
from peewee import IntegrityError
from retry import retry
from tqdm import tqdm

from . import CONFIG
from .api import CommentParser, PostCommentsParser, PostParser, WallParser
from .db import Comment, Post
from .utils import chunks

SLEEP = CONFIG.crawler.sleep_time
TIMEOUT = CONFIG.crawler.timeout
LAST_REQUEST_TIME: float = -float('inf')

_params = dict(
    v=CONFIG.crawler.vk_api_version, access_token=CONFIG.crawler.vk_user_token
)
CLIENT = Client(base_url=CONFIG.crawler.base_url, params=_params, http2=True)


def delay():
    global LAST_REQUEST_TIME
    if (delta := time() - LAST_REQUEST_TIME) < SLEEP:
        sleep(SLEEP - delta)
    LAST_REQUEST_TIME = time()


@retry(tries=3, delay=60)
def get_posts(owner_id: int, count: int, offset: int = 0) -> Mapping:
    '''Retrieve portion of posts via VK API.'''

    params = dict(
        owner_id=owner_id,
        count=count,
        offset=offset,
        extended=0,
    )

    log.info('Sent get posts response with following parameters: {}', params)

    delay()
    resp = CLIENT.get(
        f'method/execute.{CONFIG.crawler.stored_functions.get_posts}',
        params=params,
        timeout=TIMEOUT,
    )

    if resp.status_code != 200:
        raise ValueError

    json = resp.json()
    log.info(
        'Response was recieved with code {}',
        resp.status_code,
        extra={'api_response': json},
    )

    return json


def transform_wall_to_posts(json: dict) -> WallParser:
    '''Parse posts from JSON response.'''
    parsed_wall = WallParser.parse_obj(json)
    log.info('Response was parsed and contains {} posts', len(parsed_wall.posts))

    # filter artifacts with `post_id=0`
    parsed_wall.posts = [post for post in parsed_wall.posts if post.post_id]
    return parsed_wall


def load_posts(posts: list[PostParser]) -> None:
    'Save posts to the DB.'
    for post in posts:

        orm_post = Post(**post.dict())

        try:
            orm_post.save(force_insert=True)
        except IntegrityError:
            # TODO: incapsulate update into `.save()`
            orm_post.updated = datetime.now()  # type: ignore
            orm_post.save(
                only=[
                    Post.updated,
                    Post.text,
                    Post.n_likes,
                    Post.n_comments,
                    Post.n_views,
                ]
            )
    log.info('{} posts were updated in the DB', len(posts))


def etl_posts(owner_id: int, count: int, offset: int = 0) -> tuple[int, list[int]]:
    '''Extract-transfors-load potrion of posts obtained via VK API.'''
    resp = get_posts(owner_id, count=count, offset=offset)
    parsed_wall = transform_wall_to_posts(resp)
    posts = parsed_wall.posts
    load_posts(posts)

    return parsed_wall.count, [post.post_id for post in posts]


def get_all_posts(owner_id: int, limit: Optional[int] = None) -> list[int]:
    '''Extract-transfors-load posts for specified wall.'''

    # first chunk to receive total number of posts

    first_chunk_size = CONFIG.crawler.first_chunk_size
    if limit:
        first_chunk_size = min(first_chunk_size, limit)

    total_count, post_ids = etl_posts(owner_id, count=first_chunk_size)

    # the rest requests

    if limit:
        total_count = min(total_count, limit)

    log.info(
        'To get response, received `total_count` of posts equal to {}', total_count
    )

    # retrieve the rest of posts

    rest = range(CONFIG.crawler.first_chunk_size + 1, total_count + 1)

    for chunk in tqdm(
        list(chunks(rest, size=CONFIG.crawler.rest_chunks_size)),
        desc=f'posts: owner_id={owner_id}',
        leave=False,
    ):
        chunk_size = min(CONFIG.crawler.rest_chunks_size, len(chunk))
        offset = chunk[0] - 1
        log.info('Sent posts request with a `chunk_size={}`', chunk_size)
        _, new_post_ids = etl_posts(owner_id, count=chunk_size, offset=offset)
        post_ids.extend(new_post_ids)

    return post_ids


# COMMENTS


@retry(tries=3, delay=60)
def get_comments(owner_id: int, post_ids: list[int], first_offset: int = 0):

    assert len(post_ids) <= 25

    params = dict(
        owner_id=owner_id,
        offset=first_offset,
        post_ids=','.join(str(x) for x in post_ids),
    )

    log.info(
        'Sent response to get comments for following posts (owner_id={owner_id},'
        ' post_ids={post_ids})',
        owner_id=owner_id,
        post_ids=post_ids,
    )

    delay()
    resp = CLIENT.get(
        f'method/execute.{CONFIG.crawler.stored_functions.get_comments}',
        params=params,
        timeout=TIMEOUT,
    )

    if resp.status_code != 200:
        raise ValueError

    json = resp.json()
    log.info(
        'Received comments with the code {}',
        resp.status_code,
        extra={'api_response': json},
    )

    return json


def transform_post_comments(json: dict) -> PostCommentsParser:
    parsed_post_comments = PostCommentsParser.parse_obj(json)

    # filter artifacts without `owner_id`
    parsed_post_comments.comments = [
        comm for comm in parsed_post_comments.comments if comm.owner_id
    ]
    log.info('{} comments were parsed', len(parsed_post_comments.comments))
    return parsed_post_comments


def load_comments(comments: list[CommentParser]) -> None:
    for comment in comments:
        orm_comment = Comment(**comment.dict())

        try:
            orm_comment.save(force_insert=True)
        except IntegrityError:
            # TODO: incapsulate undate into `.save()`
            orm_comment.updated = datetime.now()  # type: ignore
            orm_comment.save(only=[Comment.updated, Comment.text, Comment.n_likes])

        # TODO: move to validation
        # if the threaded comment does not have an `owner_id`, set parents's one
        if thread := comment.thread:
            owner_id = comment.owner_id
            for cm in thread:
                if not cm.owner_id:
                    cm.owner_id = owner_id
            load_comments(thread)

    log.info('{} comments were added to the DB', len(comments))


def etl_comments(
    owner_id: int, post_ids: Iterable[int], offset: int = 0
) -> tuple[int, int]:

    resp = get_comments(owner_id, post_ids, offset)
    parsed_comments = transform_post_comments(resp)
    comments = parsed_comments.comments
    load_comments(comments)

    return (
        parsed_comments.next_request_must_start_with_the_corresponding_id,
        parsed_comments.offset,
    )


def get_all_comments(owner_id: int, post_ids: list[int], max_chunk=25):

    chunk_size = min(max_chunk, CONFIG.crawler.comments_chunks_size)

    for chunk in tqdm(
        list(chunks(post_ids, chunk_size)),
        desc=f'comments: owner_id={owner_id}',
        leave=False,
    ):
        try:
            post_idx, offset = etl_comments(owner_id, chunk)
            if post_idx is not None and offset != 0:
                chunk = chunk[post_idx:]
                etl_comments(owner_id, chunk, offset)
        except:
            get_all_comments(owner_id, chunk, max_chunk=max_chunk // 2)


# PAGE ALLIAS


@retry(tries=3, delay=5)
def get_id_by_name(name: str) -> Optional[int]:

    resp = CLIENT.get(
        f'method/utils.resolveScreenName',
        params={'screen_name': name},
        timeout=TIMEOUT,
    )

    if resp.status_code != 200:
        raise ValueError

    return resp.json()['response']['object_id']
