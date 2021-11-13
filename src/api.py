from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, root_validator, validator

from . import log


class VKParser(BaseModel):
    '''VK API parser base class. Any class working with VK API should be inherited from this.'''

    pass


class VKEntryParser(VKParser):
    '''Abstract representation of some entity that was published by a user, or a bot, or an community, e.g. post on a wall or a comment under the post.'''

    owner_id: Optional[int]
    from_id: int
    date: datetime
    text: str
    n_likes: Optional[int]  # entity has likes

    @root_validator(pre=True)
    def transform(cls, v):
        try:
            v['n_likes'] = v['likes']['count']
        except:
            v['n_likes'] = None
        return v


class VKPileParser(VKParser):
    '''Abstract representation of grouped set of a published entities, e.g. an list of posts on a community wall or a list of comments  under the post.'''

    @root_validator(pre=True)
    def transform(cls, v):
        try:
            return v['response']
        except KeyError:
            return []


# POSTS


class PostParser(VKEntryParser):
    post_id: int = Field(alias='id')
    is_ad: Optional[bool] = Field(alias='marked_as_ads')
    type: Optional[str] = Field(alias='post_type')

    n_comments: Optional[int] = None
    n_reposts: Optional[int] = None
    n_views: Optional[int] = None

    @root_validator
    def transform(cls, v):
        try:
            v['n_comments'] = v['comments']['count']
        except KeyError:
            v['n_comments'] = 0

        try:
            v['n_reposts'] = v['reposts']['count']
        except KeyError:
            v['n_reposts'] = 0

        try:
            v['n_views'] = v['views']['count']
        except KeyError:
            v['n_views'] = None

        return v


class WallParser(VKPileParser):
    count: int
    posts: list[PostParser] = Field([], alias='items')

    @validator('posts', pre=True)
    def items_empty_string(cls, v):
        return v or []


# COMMENTS


class CommentParser(VKEntryParser):
    owner_id: Optional[int]
    comment_id: int = Field(..., alias='id')
    from_id: int = Field(..., alias='from_id')
    post_id: Optional[int]
    date: datetime
    text: str
    n_likes: Optional[int]
    thread: 'list[CommentParser]' = []
    reply_to_comment: Optional[int]

    @root_validator(pre=True)
    def thread_getter(cls, v):
        try:
            v['thread'] = v['thread']['items']
        except KeyError:
            pass
        return v


CommentParser.update_forward_refs()


class PostCommentsParser(VKPileParser):
    next_request_must_start_with_the_corresponding_id: int = Field(
        ..., alias='post_idx'
    )
    count: int
    offset: int
    comments: list[CommentParser] = Field(alias='items')

    @validator('comments', pre=True)
    def items_empty_string(cls, v):
        return v or []

    @validator('comments')
    def cleanup(cls, v):
        return [cmnt for cmnt in v if cmnt.post_id and cmnt.comment_id]
