from werkzeug.routing import Map
from werkzeug.routing import Rule
from werkzeug.routing import Submount

map = Map(
    [
        Rule("/", endpoint="#language_select"),
        Submount(
            "/<string(length=2):lang_code>",
            [
                Rule("/", endpoint="index"),
                Rule("/about", endpoint="about"),
                Rule("/blog/", endpoint="blog/index"),
                Rule("/blog/<int:post_id>", endpoint="blog/show"),
            ],
        ),
    ]
)
