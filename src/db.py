from peewee import (
    BooleanField,
    CompositeKey,
    DateTimeField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)

db = SqliteDatabase('data/vk.db')


class BaseModel(Model):
    class Meta:
        database = db


class Post(BaseModel):

    owner_id = IntegerField()
    post_id = IntegerField()
    from_id = IntegerField()

    is_ad = BooleanField()
    type = TextField()

    text = TextField()
    date = DateTimeField()
    updated = DateTimeField(null=True)
    n_comments = IntegerField()
    n_likes = IntegerField()
    n_reposts = IntegerField()
    n_views = IntegerField(null=True)

    class Meta:
        primary_key = CompositeKey('owner_id', 'post_id')


class Comment(BaseModel):

    # BUG: When use the following ForeignKey, strange IntegrityError in src.load_comments occurs
    # post = ForeignKeyField(Post, field='post_id', backref='comments', null=True)

    owner_id = IntegerField()
    post_id = IntegerField()
    comment_id = IntegerField()
    from_id = IntegerField()

    text = TextField()
    date = DateTimeField()
    updated = DateTimeField(null=True)
    n_likes = IntegerField(null=True)
    reply_to_comment = IntegerField(null=True)

    class Meta:
        primary_key = CompositeKey('owner_id', 'post_id', 'comment_id')


db.connect()
db.create_tables([Post, Comment])
