"Template tags for rendering snippet content."

from django import template
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from scribbler.models import Scribble
from scribbler.views import build_scribble_context


register = template.Library()


class ScribbleNode(template.Node):
    "Render snippet or default block content."
    
    child_nodelists = ('nodelist_default', )

    def __init__(self, slug, nodelist, raw):
        self.slug = template.Variable(slug)
        self.nodelist_default = nodelist
        self.raw = raw

    def render(self, context):
        slug = self.slug.resolve(context)
        request = context.get('request', None)
        if request is None:
            if settings.DEBUG:
                msg = u'"django.core.context_processors.request" is required to use django-scribble'
                raise ImproperlyConfigured(msg)
            else:
                return u''
        try:
            scribble = Scribble.objects.get(slug=slug, url=request.path)
        except Scribble.DoesNotExist:
            scribble = Scribble(slug=slug, url=request.path, content=self.raw)
        if scribble:
            nodelist = template.Template(scribble.content)
        else:
            nodelist = self.nodelist_default
        scribble_context = build_scribble_context(scribble, request)
        return nodelist.render(scribble_context)


def rebuild_template_string(tokens):
    "Reconstruct the original template from a list of tokens."
    result = u''
    for token in tokens:
        value = token.contents
        if token.token_type == template.TOKEN_VAR:
            value = u'{0} {1} {2}'.format(
                template.VARIABLE_TAG_START,
                value,
                template.VARIABLE_TAG_END,
            )
        elif token.token_type == template.TOKEN_BLOCK:
            value = u'{0} {1} {2}'.format(
                template.BLOCK_TAG_START,
                value,
                template.BLOCK_TAG_END,
            )
        elif token.token_type == template.TOKEN_COMMENT:
            value = u'{0} {1} {2}'.format(
                template.COMMENT_TAG_START,
                value,
                template.COMMENT_TAG_END,
            )
        result = u'{0}{1}'.format(result, value)
    return result     


@register.tag
def scribble(parser, token):
    """
    Renders a scribble by slug. First looks for a scribble matching the
    current url and slug then looks for shared scribbles by slug.

    Usage:
    {% scribble 'sidebar' %}
        <p>This is the default.</p>
    {% endscribble %}
    """
    try:
        tag_name, slug = token.split_contents()
    except ValueError:
        msg = u"{0} tag requires exactly one argument.".format(*token.contents.split())
        raise template.TemplateSyntaxError(msg)
    # Save original token state
    tokens = parser.tokens[:]
    nodelist = parser.parse(('endscribble', ))
    # Remaining tokens are inside the block
    tokens = filter(lambda t: t not in parser.tokens, tokens)
    parser.delete_first_token()
    raw = rebuild_template_string(tokens)
    return ScribbleNode(slug=slug, nodelist=nodelist, raw=raw)
