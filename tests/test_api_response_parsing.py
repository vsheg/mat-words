from os import listdir

from src.api import PostCommentsParser, WallParser


def test_wall_get_response():
    WallParser.parse_file('tests/data/wall_get_response.json')


def test_wall_get_comments_response():
    PostCommentsParser.parse_file('tests/data/wall_getComments_response.json')
