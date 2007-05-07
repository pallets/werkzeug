from i18nurls.application import TemplateResponse, Response, expose


@expose('index')
def index(req):
    return TemplateResponse('index.html', title='Index')

@expose('about')
def about(req):
    return TemplateResponse('about.html', title='About')

@expose('blog/index')
def blog_index(req):
    return TemplateResponse('blog.html', title='Blog Index', mode='index')

@expose('blog/show')
def blog_show(req, post_id):
    return TemplateResponse('blog.html', title='Blog Post #%d' % post_id,
                            post_id=post_id, mode='show')

def page_not_found(req):
    return Response('<h1>Page Not Found</h1>', mimetype='text/html')
