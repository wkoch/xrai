from slugify.__main__ import parse_args,slugify_params
from slugify import slugify
params=slugify_params(parse_args(['slugify','--regex-pattern','[^-a-z0-9_]+','___This is a test___']))
assert params.get('regex_pattern')=='[^-a-z0-9_]+'
assert slugify(**params)=='___this-is-a-test___'
