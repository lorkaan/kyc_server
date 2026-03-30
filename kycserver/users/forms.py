from django import forms

from users.models import FieldPermissions

class FieldPermissionsForm(forms.ModelForm):
    view = forms.BooleanField(required=False)
    edit = forms.BooleanField(required=False)
    add = forms.BooleanField(required=False)
    delete = forms.BooleanField(required=False)

    class Meta:
        model = FieldPermissions
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance:
            self.fields["view"].initial = self.instance.has_flag(FieldPermissions.Flag.VIEW)
            self.fields["edit"].initial = self.instance.has_flag(FieldPermissions.Flag.EDIT)
            self.fields["add"].initial = self.instance.has_flag(FieldPermissions.Flag.ADD)
            self.fields["delete"].initial = self.instance.has_flag(FieldPermissions.Flag.DELETE)

    def save(self, commit=True):
        instance = super().save(commit=False)

        permission = 0
        if self.cleaned_data.get("view"):
            permission |= FieldPermissions.Flag.VIEW
        if self.cleaned_data.get("edit"):
            permission |= FieldPermissions.Flag.EDIT
        if self.cleaned_data.get("add"):
            permission |= FieldPermissions.Flag.ADD
        if self.cleaned_data.get("delete"):
            permission |= FieldPermissions.Flag.DELETE

        instance.permission = permission

        if commit:
            instance.save()

        return instance