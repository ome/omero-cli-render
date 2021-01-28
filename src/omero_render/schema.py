import json
from jsonschema import Draft7Validator
from pkgutil import get_data
import yaml


def _validate(schema_name, renderdef):
    schemastr = get_data('omero_render', schema_name)
    yml = yaml.safe_load(schemastr)
    # Hack to expand anchors
    # https://stackoverflow.com/a/64993515
    schema = json.loads(json.dumps(yml))
    v = Draft7Validator(schema)
    # print(yaml.dump(schema))
    # print(renderdef)
    # Hack to ensure YAML integer keys are JSON strings
    renderdef_json = json.loads(json.dumps(renderdef))

    if not v.is_valid(renderdef_json):
        errs = '\n\n** '.join(
            ['Invalid definition'] +
            ['\n\n'.join(str(e) for e in v.iter_errors(renderdef_json))])
        raise ValueError(errs)


def validate_renderdef(renderdef):
    _validate('renderdef-schema.yaml', renderdef)


def validate_renderdef_batch(renderdef):
    _validate('renderdef-batch-schema.yaml', renderdef)
