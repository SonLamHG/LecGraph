"""Tests for the knowledge extractor."""

from src.pipeline.extractor import _parse_json_response


class TestParseJsonResponse:
    def test_plain_json_array(self):
        text = '[{"name": "test", "value": 1}]'
        result = _parse_json_response(text)
        assert isinstance(result, list)
        assert result[0]["name"] == "test"

    def test_json_in_code_block(self):
        text = '```json\n[{"name": "test"}]\n```'
        result = _parse_json_response(text)
        assert isinstance(result, list)
        assert result[0]["name"] == "test"

    def test_json_object(self):
        text = '{"title": "Test", "key_quotes": []}'
        result = _parse_json_response(text)
        assert isinstance(result, dict)
        assert result["title"] == "Test"

    def test_json_with_whitespace(self):
        text = '  \n  [{"name": "test"}]  \n  '
        result = _parse_json_response(text)
        assert result[0]["name"] == "test"

    def test_code_block_without_language(self):
        text = '```\n{"key": "value"}\n```'
        result = _parse_json_response(text)
        assert result["key"] == "value"
