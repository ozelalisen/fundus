import gzip
import json
from os.path import exists
from pathlib import Path
from typing import Any, Dict, List

import lxml.html
import pytest

from fundus import __development_base_path__ as root_path
from fundus.parser.base_parser import Attribute, AttributeCollection, BaseParser
from fundus.publishers import PublisherCollection
from fundus.publishers.base_objects import PublisherEnum
from tests.resources import attribute_annotations_mapping
from tests.resources.parser.test_data import __module_path__ as test_resource_path


def load_html(publisher: PublisherEnum) -> str:
    relative_file_path = Path(f"{publisher.__class__.__name__.lower()}/{publisher.name}.html.gz")
    absolute_path = test_resource_path / relative_file_path

    with open(absolute_path, "rb") as file:
        content = file.read()

    decompressed_content = gzip.decompress(content)
    result = decompressed_content.decode("utf-8")
    return result


def load_data(publisher: PublisherEnum) -> Dict[str, Any]:
    relative_file_path = Path(f"{publisher.__class__.__name__.lower()}/{publisher.name}.json")
    absolute_path = test_resource_path / relative_file_path

    with open(absolute_path, "r", encoding="utf-8") as file:
        content = file.read()

    data = json.loads(content)
    if isinstance(data, dict):
        return data
    else:
        raise ValueError("Unknown json format")


def test_supported():
    relative_path = Path("doc/supported_news.md")
    supported_news_path = root_path / relative_path

    if not exists(supported_news_path):
        raise FileNotFoundError(f"The '{relative_path}' is missing. Run 'python -m generate_tables'")

    with open(supported_news_path, "rb") as file:
        content = file.read()

    root = lxml.html.fromstring(content)
    parsed_names: List[str] = root.xpath("//table[contains(@class,'source')]//code/text()")
    for publisher in PublisherCollection:
        assert (
            publisher.name in parsed_names
        ), f"Publisher {publisher.name} is not included in README.md. Run 'python -m fundus.utils.generate_tables'"


class TestBaseParser:
    def test_functions_iter(self, parser_with_function_test, parser_with_static_method):
        assert len(BaseParser.functions()) == 0
        assert len(parser_with_static_method.functions()) == 0
        assert len(parser_with_function_test.functions()) == 1
        assert parser_with_function_test.functions().names == ["test"]

    def test_attributes_iter(self, parser_with_attr_title, parser_with_static_method):
        assert len(BaseParser.attributes()) == 0
        assert len(parser_with_static_method.attributes()) == 0
        assert len(parser_with_attr_title.attributes()) == 1
        assert parser_with_attr_title.attributes().names == ["title"]

    def test_supported_unsupported(self, parser_with_validated_and_unvalidated):
        parser = parser_with_validated_and_unvalidated
        assert len(parser.attributes()) == 2
        assert parser.attributes().validated.names == AttributeCollection(parser.validated).names
        assert parser.attributes().unvalidated.names == AttributeCollection(parser.unvalidated).names


@pytest.mark.parametrize(
    "publisher", list(PublisherCollection), ids=[publisher.name for publisher in PublisherCollection]
)
class TestParser:
    def test_annotations(self, publisher: PublisherEnum) -> None:
        parser = publisher.parser
        for attr in parser.attributes().validated:
            if annotation := attribute_annotations_mapping[attr.__name__]:
                assert (
                    attr.__annotations__.get("return") == annotation
                ), f"Attribute {attr.__name__} for {parser.__name__} failed"
            else:
                raise KeyError(f"Unsupported attribute '{attr.__name__}'")

    def test_parsing(self, publisher: PublisherEnum) -> None:
        html = load_html(publisher)
        comparative_data = load_data(publisher)
        parser = publisher.parser()

        # enforce test coverage
        attrs_required_to_cover = {"title", "authors", "topics"}
        supported_attrs = set(parser.attributes().names)
        missing_attrs = attrs_required_to_cover & supported_attrs - set(comparative_data.keys())
        assert not missing_attrs, f"Test JSON does not cover the following attribute(s): {missing_attrs}"

        # compare data
        result = parser.parse(html, "raise")
        for key in comparative_data.keys():
            assert comparative_data[key] == result[key]

    def test_reserved_attribute_names(self, publisher: PublisherEnum):
        parser = publisher.parser
        for attr in attribute_annotations_mapping.keys():
            if value := getattr(parser, attr, None):
                assert isinstance(value, Attribute), f"The name '{attr}' is reserved for attributes only."
