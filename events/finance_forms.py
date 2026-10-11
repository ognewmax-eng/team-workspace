from decimal import Decimal
from django import forms
from .models import EventBudget, EventBudgetLine


class BudgetForm(forms.ModelForm):
    class Meta:
        model=EventBudget
        fields=['allocated','funding_source']


class BudgetLineForm(forms.ModelForm):
    class Meta:
        model=EventBudgetLine
        fields=['title','category','quantity','unit','unit_price','status','purchased_quantity','actual_amount','paid_amount','supplier','document_number','due_date','note']
        widgets={'due_date':forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}),'note':forms.Textarea(attrs={'rows':3})}

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for name in ['purchased_quantity','actual_amount','paid_amount']:self.fields[name].required=False
        for field in self.fields.values():field.widget.attrs.setdefault('class','form-control')

    def clean(self):
        data=super().clean()
        for name in ['purchased_quantity','actual_amount','paid_amount']:data[name]=data.get(name) or Decimal('0')
        if data['paid_amount']>data['actual_amount']:self.add_error('paid_amount','Оплата не может превышать стоимость закупки / обязательство.')
        if data.get('quantity') and data.get('unit_price') is not None and data['quantity']*data['unit_price']>Decimal('999999999999.99'):
            self.add_error('unit_price','Сумма одной позиции слишком велика.')
        return data
