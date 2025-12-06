# inventory/forms.py
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import PurchaseBill, SalesBill, Customer, Supplier
from django.contrib.auth.decorators import login_required


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Password'
    }))


class PurchaseBillForm(forms.ModelForm):
    class Meta:
        model = PurchaseBill
        fields = ["supplier", "bill_number", "bill_date", "payment_mode"]
        widgets = {
            "bill_date": forms.DateInput(attrs={"type": "date"}),
        }


class SalesBillForm(forms.ModelForm):
    class Meta:
        model = SalesBill
        fields = ['payment_mode']


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'address', 'due_date']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "mobile", "address"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "mobile": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

