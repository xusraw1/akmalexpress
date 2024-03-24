from django.shortcuts import render, redirect
from .forms import CreateProductForm
from django.contrib import messages


def index(request):
    return render(request, 'index.html')


def create_product(request):
    form = CreateProductForm()
    context = {'form': form}
    if request.method == 'POST':
        form = CreateProductForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.username = request.user
            product.save()
            messages.success(request, "Продукт добавлен")
            return redirect('/')
        messages.error(request, "Форма заполнена неверно")
        return render(request, 'akmalexpress/create_product.html', context)
    return render(request, 'akmalexpress/create_product.html', context)
