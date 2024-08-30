import json
import os
import re
import shutil

import docutils.core
import frontmatter
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError
from sphinx.util.matching import get_matching_files


def extract_markdown_tags(file: str) -> list[str] | None:
    try:
        tags = frontmatter.load(file)["tags"]
        if tags:
            return tags.split()
    except AttributeError as err:
        message = "{}: tags must be string".format(file)
        raise ExtensionError(message, err)
    except KeyError:
        return None


def extract_rst_tags(file: str) -> list[str] | None:
    with open(file) as f:
        dom = docutils.core.publish_doctree(f.read()).asdom()
    try:
        fields = dom.getElementsByTagName("docinfo")[0].getElementsByTagName("field")
    except IndexError:
        return None
    for field in fields:
        name = field.getElementsByTagName("field_name")[0].firstChild.nodeValue
        if name == "tags":
            body = field.getElementsByTagName("field_body")[0].firstChild
            if body:
                return body.firstChild.nodeValue.split()
    return None


def extract_jupyter_tags(file: str) -> list[str] | None:
    try:
        with open(file) as f:
            tags = json.load(f)["metadata"]["tags"]
            if tags:
                return tags.split()
    except AttributeError as err:
        message = "{}: tags must be string".format(file)
        raise ExtensionError(message, err)
    except KeyError:
        return None


def ensure_dir(parent: str, name: str) -> str:
    path = os.path.join(parent, name)
    if os.path.exists(path):
        shutil.rmtree(path)
    os.mkdir(path)
    return path


def validate_tags(file: str, tags: list[str]) -> None:
    for tag in tags:
        if not re.match("^[a-z0-9-]+$", tag):
            message = "{}: invalid tag {}".format(file, tag)
            raise ExtensionError(message)
    return None


def extract_tags(app: Sphinx) -> dict[str, list[str]]:
    result = dict()
    extractors = {
        ".ipynb": extract_jupyter_tags,
        ".md": extract_markdown_tags,
        ".Rmd": extract_markdown_tags,
        ".rst": extract_rst_tags,
    }
    suffixes = list(app.config.source_suffix.keys())
    for suffix in suffixes:
        if suffix in extractors:
            files = get_matching_files(
                app.srcdir, ["**{}".format(suffix)], app.config.exclude_patterns
            )
            for file in files:
                tags = extractors[suffix](os.path.join(app.srcdir, file))
                if type(tags) is list:
                    if tags:
                        validate_tags(file, tags)
                        result[file] = tags
                    else:
                        message = "{}: no valid tags detected".format(file)
                        raise ExtensionError(message)
    return result


def invert_dict(dictionary: dict[str, list[str]]) -> dict[str, list[str]]:
    result = dict()
    for key, values in dictionary.items():
        for value in values:
            result.setdefault(value, []).append(key)
    return result


def write_files(tags: dict[str, list[str]], root: str) -> None:
    labels = []
    header = [
        "---",
        "orphan:",
        "nosearch:",
        "html_theme.sidebar_secondary.remove: true",
        "---",
    ]
    tags_dir = os.path.basename(root)
    for tag, files in tags.items():
        label = "- [{0} ({1})](/{2}/{0}.md)".format(tag, len(files), tags_dir)
        labels.append(label)
        lines = header + ["# {}".format(tag)]
        for file in sorted(files):
            lines.append("- [](/{})".format(file))
        path = os.path.join(root, "{}.md".format(tag))
        with open(file=path, mode="w") as f:
            f.write("\n".join(lines) + "\n")
    if labels:
        with open(file=os.path.join(root, "index.md"), mode="w") as f:
            conent = header + ["# Tags"] + sorted(labels)
            f.write("\n".join(conent) + "\n")
    return None


def preprocess_tags(app: Sphinx) -> None:
    path = ensure_dir(app.srcdir, "tags")
    tags = invert_dict(extract_tags(app))
    write_files(tags, path)
    return None


def setup(app: Sphinx) -> None:
    app.connect(event="builder-inited", callback=preprocess_tags)
    return None
