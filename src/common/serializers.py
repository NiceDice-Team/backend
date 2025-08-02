from rest_framework import serializers


class ExampleIgnoringModelSerializer(serializers.ModelSerializer):
    def build_standard_field(self, field_name, model_class):
        klass, field_kwargs = super().build_standard_field(field_name, model_class)
        field_kwargs.pop('example', None)
        return klass, field_kwargs
