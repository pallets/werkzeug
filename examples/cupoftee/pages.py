from functools import reduce

from werkzeug.exceptions import NotFound
from werkzeug.utils import redirect

from .application import Page
from .utils import unicodecmp


class ServerList(Page):
    url_rule = "/"

    def order_link(self, name, title):
        cls = ""
        link = f"?order_by={name}"
        desc = False
        if name == self.order_by:
            desc = not self.order_desc
            cls = f' class="{"down" if desc else "up"}"'
        if desc:
            link += "&amp;dir=desc"
        return f'<a href="{link}"{cls}>{title}</a>'

    def process(self):
        self.order_by = self.request.args.get("order_by") or "name"
        sort_func = {
            "name": lambda x: x,
            "map": lambda x: x.map,
            "gametype": lambda x: x.gametype,
            "players": lambda x: x.player_count,
            "progression": lambda x: x.progression,
        }.get(self.order_by)
        if sort_func is None:
            return redirect(self.url_for("serverlist"))

        self.servers = self.cup.server_browser.servers.values()
        self.servers.sort(key=sort_func)
        if self.request.args.get("dir") == "desc":
            self.servers.reverse()
            self.order_desc = True
        else:
            self.order_desc = False

        self.players = reduce(lambda a, b: a + b.players, self.servers, [])
        self.players = sorted(self.players, key=lambda a, b: unicodecmp(a.name, b.name))


class Server(Page):
    url_rule = "/server/<id>"

    def process(self, id):
        try:
            self.server = self.cup.server_browser.servers[id]
        except KeyError:
            raise NotFound()


class Search(Page):
    url_rule = "/search"

    def process(self):
        self.user = self.request.args.get("user")
        if self.user:
            self.results = []
            for server in self.cup.server_browser.servers.values():
                for player in server.players:
                    if player.name == self.user:
                        self.results.append(server)


class MissingPage(Page):
    def get_response(self):
        response = super().get_response()
        response.status_code = 404
        return response
