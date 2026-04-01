from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views import View
from django.views.generic import ListView, DetailView, UpdateView, CreateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError
from catalog.models import Category
from catalog.forms.category_form import CategoryForm
from catalog.services import CategoryService

class CategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for all categories.
    Accessible to all users with 'view_category' permission.
    """
    model = Category
    template_name = 'catalog/category_list.html'
    context_object_name = 'categories'
    permission_required = 'catalog.view_category'
    raise_exception = True

    def get_queryset(self):
        return CategoryService.get_active_queryset()

class CategoryTrashListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for soft-deleted categories (Trash).
    Accessible only to Executives with 'delete_category' permission.
    """
    model = Category
    template_name = 'catalog/category_trash_list.html'
    context_object_name = 'categories'
    permission_required = 'catalog.delete_category'
    # Use delete permission as it regulates trash access
    raise_exception = True

    def get_queryset(self):
        return CategoryService.list_deleted()

class CategoryDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detailed view for a single category.
    """
    model = Category
    template_name = 'catalog/category_detail.html'
    context_object_name = 'category'
    permission_required = 'catalog.view_category'
    raise_exception = True

    def get_queryset(self):
        # Prevent accessing deleted categories from the main detail view
        return CategoryService.get_active_queryset()

class CategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    View for creating a new Category via CategoryService.
    Standardized as a CreateView for architectural consistency.
    """
    model = Category
    form_class = CategoryForm
    template_name = 'catalog/category_form.html'
    permission_required = 'catalog.add_category'
    raise_exception = True
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "New Category"
        context['action_label'] = "Create Category"
        return context

    def form_valid(self, form):
        try:
            # Use CategoryService.create for consistent business logic
            category = CategoryService.create(
                name=form.cleaned_data['name'],
                code=form.cleaned_data['code'],
                parent=form.cleaned_data['parent'],
                note=form.cleaned_data['note'],
                user=self.request.user
            )
            messages.success(self.request, f"Category '{category.name}' created successfully!")
            return redirect('catalog:category-list')
        except Exception as e:
            messages.error(self.request, f"Error creating category: {str(e)}")
            return self.form_invalid(form)

class CategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    View for updating an existing Category via CategoryService.
    """
    model = Category
    form_class = CategoryForm
    template_name = 'catalog/category_form.html'
    permission_required = 'catalog.change_category'
    raise_exception = True

    def get_queryset(self):
        return CategoryService.get_active_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Category: {self.object.name}"
        context['action_label'] = "Update Category"
        return context

    def form_valid(self, form):
        try:
            CategoryService.update(
                self.object,
                user=self.request.user,
                name=form.cleaned_data['name'],
                code=form.cleaned_data['code'],
                parent=form.cleaned_data['parent'],
                note=form.cleaned_data['note']
            )
            messages.success(self.request, f"Category '{self.object.name}' updated successfully!")
            return redirect('catalog:category-detail', pk=self.object.pk)
        except Exception as e:
            messages.error(self.request, f"Error updating category: {str(e)}")
            return self.form_invalid(form)

class CategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    View for soft-deleting a Category via CategoryService.
    Ensures hierarchical safety (cannot delete if active children exist).
    """
    model = Category
    template_name = 'catalog/category_confirm_delete.html'
    permission_required = 'catalog.delete_category'
    success_url = reverse_lazy('catalog:category-list')
    raise_exception = True

    def get_queryset(self):
        return CategoryService.get_active_queryset()

    def form_valid(self, form):
        """
        Executes the soft-delete via CategoryService.
        Handles ValidationErrors gracefully (e.g. category has children).
        """
        try:
            CategoryService.soft_delete(self.get_object(), user=self.request.user)
            messages.success(self.request, f"Category '{self.object.name}' deleted successfully.")
            return redirect(self.success_url)
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.get(self.request) # Re-render confirmation with error
        except Exception as e:
            messages.error(self.request, f"Unexpected error: {str(e)}")
            return self.get(self.request)

class CategoryRestoreView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view for restoring a soft-deleted Category via CategoryService.
    """
    permission_required = 'catalog.delete_category'
    raise_exception = True

    def post(self, request, pk):
        category = get_object_or_404(Category, pk=pk, is_deleted=True)
        try:
            CategoryService.restore(category, user=request.user)
            messages.success(request, f"Category '{category.name}' restored successfully.")
            return redirect('catalog:category-list')
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('catalog:category-trash')
        except Exception as e:
            messages.error(request, f"Unexpected error while restoring: {str(e)}")
            return redirect('catalog:category-trash')
