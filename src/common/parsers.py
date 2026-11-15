from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


class JSONObjectParser(JSONParser):

    def parse(self, stream, media_type=None, parser_context=None):
        data = super().parse(stream, media_type=media_type, parser_context=parser_context)
        if not isinstance(data, dict):
            raise ParseError('JSON parse error - a JSON object is expected as the request body.')
        return data
