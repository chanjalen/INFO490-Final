from django import forms
from django.contrib.auth.forms import PasswordChangeForm as _DjangoPasswordChangeForm
from django.contrib.auth.models import User


class SignupForm(forms.Form):
    username = forms.CharField(max_length=150, label="Username")
    email = forms.EmailField(required=False, label="Email (optional)")
    password = forms.CharField(
        widget=forms.PasswordInput, min_length=8, label="Password"
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username


class DisplayNameForm(forms.Form):
    display_name = forms.CharField(
        max_length=80,
        required=False,
        label="Display name",
        widget=forms.TextInput(attrs={"placeholder": "Your display name"}),
    )


class EmailUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if email and qs.exists():
            raise forms.ValidationError("That email is already associated with another account.")
        return email


class PasswordChangeForm(_DjangoPasswordChangeForm):
    """Thin wrapper so templates can import from one place."""
    pass


class DeleteAccountForm(forms.Form):
    confirm = forms.CharField(
        label='Type "DELETE" to confirm',
        widget=forms.TextInput(attrs={"placeholder": "DELETE"}),
    )

    def clean_confirm(self):
        value = self.cleaned_data.get("confirm", "")
        if value != "DELETE":
            raise forms.ValidationError('Please type DELETE exactly to confirm.')
        return value
