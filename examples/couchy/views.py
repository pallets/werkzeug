from werkzeug.utils import redirect
from werkzeug.exceptions import NotFound
from couchy.utils import render_template, expose, \
     validate_url, url_for, Pagination
from couchy.models import URL


@expose('/')
def new(request):
    error = url = ''
    if request.method == 'POST':
        url = request.form.get('url')
        alias = request.form.get('alias')
        if not validate_url(url):
            error = "I'm sorry but you cannot shorten this URL."
        elif alias:
            if len(alias) > 140:
                error = 'Your alias is too long'
            elif '/' in alias:
                error = 'Your alias might not include a slash'
            elif URL.load(alias):
                error = 'The alias you have requested exists already'
        if not error:
            url = URL(target=url, public='private' not in request.form, shorty_id=alias if alias else None)
            url.store()
            uid = url.id
            return redirect(url_for('display', uid=uid))
    return render_template('new.html', error=error, url=url)

@expose('/display/<uid>')
def display(request, uid):
    url = URL.load(uid)
    if not url:
        raise NotFound()
    return render_template('display.html', url=url)

@expose('/u/<uid>')
def link(request, uid):
    url = URL.load(uid)
    if not url:
        raise NotFound()
    return redirect(url.target, 301)

@expose('/list/', defaults={'page': 1})
@expose('/list/<int:page>')
def list(request, page):
    def wrap(doc):
        data = doc.value
        data['_id'] = doc.id
        return URL.wrap(data)

    code = '''function(doc) { if (doc.public){ map([doc._id], doc); }}'''
    docResults = URL.query(code)
    results = [wrap(doc) for doc in docResults]
    pagination = Pagination(results, 1, page, 'list')
    if pagination.page > 1 and not pagination.entries:
        raise NotFound()
    return render_template('list.html', pagination=pagination)

def not_found(request):
    return render_template('not_found.html')
