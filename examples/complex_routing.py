from werkzeug.routing import Map, Rule, Subdomain, Submount, EndpointPrefix

m = Map([
    # Static URLs
    EndpointPrefix('static/', [
        Rule('/', endpoint='index'),
        Rule('/about', endpoint='about'),
        Rule('/help', endpoint='help'),
    ]),
    # Knowledge Base
    Subdomain('kb', [EndpointPrefix('kb/', [
        Rule('/', endpoint='index'),
        Submount('/browse', [
            Rule('/', endpoint='browse'),
            Rule('/<int:id>/', defaults={'page': 1}, endpoint='browse'),
            Rule('/<int:id>/<int:page>', endpoint='browse')
        ])
    ])])
])
