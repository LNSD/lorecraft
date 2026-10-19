"""Generate the JSON Schemas of the specification files.

The schemas go into `docs/schemas/`, unless `--outdir` names another directory.

Each schema is rendered from the pydantic model the package deserializes the file with, so the schema an editor
applies and the validation the check runs come from one declaration; nothing here restates a field. The models carry
everything an editor is shown: descriptions as field docstrings, examples and bounds in `Field`, titles and whole
examples in `model_config`.
"""

import argparse
import json
from pathlib import Path
from typing import Final

from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema

from lorecraft.project.schemas import StructureFile
from lorecraft.schemas.agent_skills_frontmatter import SkillFrontmatter

_JSON_SCHEMA_DIALECT: Final[str] = 'https://json-schema.org/draft/2020-12/schema'
_DEFAULT_OUTDIR: Final[Path] = Path('docs/schemas')


class _WithoutPropertyTitles(GenerateJsonSchema):
    """pydantic's generator, without the title it gives every property: a property's key already names it."""

    def field_title_should_be_set(self, schema: object) -> bool:
        """Never title a property.

        Args:
            schema: The schema of the field, which the answer does not depend on.
        """
        return False


def _unwrap_descriptions(node: object) -> None:
    """Rejoin the lines each description's docstring was wrapped at, keeping its paragraph breaks.

    An editor wraps the text to its own width.

    Args:
        node: A schema, or a part of one, rewritten in place wherever a `description` key holds a string.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == 'description' and isinstance(value, str):
                paragraphs = value.split('\n\n')
                node[key] = '\n\n'.join(' '.join(paragraph.split()) for paragraph in paragraphs)
            else:
                _unwrap_descriptions(value)
    elif isinstance(node, list):
        for item in node:
            _unwrap_descriptions(item)


def write_schema(file_model: type[BaseModel], path: Path) -> Path:
    """Write one file model's JSON Schema, led by the dialect it is written in.

    Args:
        file_model: The model the package deserializes the file with.
        path: The file to write; its directory is created if absent.

    Returns:
        The path written, which is `path`.
    """
    schema = file_model.model_json_schema(schema_generator=_WithoutPropertyTitles)
    _unwrap_descriptions(schema)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {'$schema': _JSON_SCHEMA_DIALECT, **schema}
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return path


def main() -> None:
    """Write the schema of every specification file model into the output directory, and print where each went.

    The output directory is the `--outdir` option, and `docs/schemas` when it is absent.
    """
    parser = argparse.ArgumentParser(description='Generate the JSON Schemas of the specification files.')
    parser.add_argument(
        '--outdir',
        type=Path,
        default=_DEFAULT_OUTDIR,
        help='the directory the schemas are written into (default: %(default)s)',
    )
    outdir: Path = parser.parse_args().outdir

    print('Generating the specification schemas...')
    schemas = {
        'structure.spec.json': StructureFile,
        'skill-frontmatter.spec.json': SkillFrontmatter,
    }
    for filename, file_model in schemas.items():
        written_path = write_schema(file_model, outdir / filename)
        print(f'  {written_path}')


if __name__ == '__main__':
    main()
