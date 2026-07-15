from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views import View
from django.views.generic import ListView, DetailView, UpdateView, CreateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError

from common.models import Individual
from common.forms.individual_form import IndividualForm
from common.services.individual_service import IndividualService


class IndividualListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for all active individuals.
    """
    model = Individual
    template_name = 'common/individual_list.html'
    context_object_name = 'individuals'
    permission_required = 'common.view_individual'
    raise_exception = True

    def get_queryset(self):
        return IndividualService.list_active()


class IndividualTrashListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for soft-deleted individuals (Trash).
    """
    model = Individual
    template_name = 'common/individual_trash_list.html'
    context_object_name = 'individuals'
    permission_required = 'common.delete_individual'
    raise_exception = True

    def get_queryset(self):
        return IndividualService.list_deleted()


class IndividualDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detailed view for a single individual.
    """
    model = Individual
    template_name = 'common/individual_detail.html'
    context_object_name = 'individual'
    permission_required = 'common.view_individual'
    raise_exception = True

    def get_queryset(self):
        return IndividualService.get_active_queryset()


class IndividualCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    View for creating a new Individual.
    """
    model = Individual
    form_class = IndividualForm
    template_name = 'common/individual_form.html'
    permission_required = 'common.add_individual'
    raise_exception = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "New Individual"
        context['action_label'] = "Create Record"
        return context

    def form_valid(self, form):
        try:
            individual = IndividualService.create(
                created_by=self.request.user,
                **form.cleaned_data
            )
            messages.success(self.request, f"Individual '{str(individual)}' created successfully!")
            return redirect('common:individual-list')
        except Exception as e:
            messages.error(self.request, f"Error creating record: {str(e)}")
            return self.form_invalid(form)


class IndividualUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    View for updating an existing Individual.
    """
    model = Individual
    form_class = IndividualForm
    template_name = 'common/individual_form.html'
    permission_required = 'common.change_individual'
    raise_exception = True

    def get_queryset(self):
        return IndividualService.get_active_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Individual: {str(self.object)}"
        context['action_label'] = "Update Record"
        return context

    def form_valid(self, form):
        try:
            IndividualService.update(
                self.object,
                updated_by=self.request.user,
                **form.cleaned_data
            )
            messages.success(self.request, f"Individual '{str(self.object)}' updated successfully!")
            return redirect('common:individual-detail', pk=self.object.pk)
        except Exception as e:
            messages.error(self.request, f"Error updating record: {str(e)}")
            return self.form_invalid(form)


class IndividualDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    View for soft-deleting an Individual.
    """
    model = Individual
    template_name = 'common/individual_confirm_delete.html'
    permission_required = 'common.delete_individual'
    success_url = reverse_lazy('common:individual-list')
    raise_exception = True

    def get_queryset(self):
        return IndividualService.get_active_queryset()

    def form_valid(self, form):
        try:
            IndividualService.soft_delete(self.get_object(), user=self.request.user)
            messages.success(self.request, f"Individual '{str(self.object)}' moved to trash.")
            return redirect(self.success_url)
        except Exception as e:
            messages.error(self.request, f"Unexpected error: {str(e)}")
            return self.get(self.request)


class IndividualRestoreView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view for restoring a soft-deleted Individual.
    """
    permission_required = 'common.delete_individual'
    raise_exception = True

    def post(self, request, pk):
        individual = get_object_or_404(Individual, pk=pk, is_deleted=True)
        try:
            IndividualService.restore(individual, user=request.user)
            messages.success(request, f"Individual '{str(individual)}' restored successfully.")
            return redirect('common:individual-list')
        except Exception as e:
            messages.error(request, f"Unexpected error while restoring: {str(e)}")
            return redirect('common:individual-trash')
