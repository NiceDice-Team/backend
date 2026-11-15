from rest_framework import serializers


class FullBodySerializerMixin:

    @property
    def partial(self):
        return False

    @partial.setter
    def partial(self, value):
        pass


class ExampleIgnoringModelSerializer(serializers.ModelSerializer):
    def build_standard_field(self, field_name, model_class):
        klass, field_kwargs = super().build_standard_field(field_name, model_class)
        field_kwargs.pop('example', None)
        return klass, field_kwargs


class ErrorMessageSerializer(serializers.Serializer):
    error = serializers.CharField()


class DetailMessageSerializer(serializers.Serializer):
    detail = serializers.CharField()


class CodedErrorSerializer(serializers.Serializer):
    type = serializers.CharField(required=False)
    errors = serializers.JSONField(required=False)
    code = serializers.CharField(required=False)
    field = serializers.CharField(required=False, allow_null=True)
    message = serializers.CharField(required=False)
    error = serializers.CharField(required=False)
    detail = serializers.CharField(required=False)


class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()
