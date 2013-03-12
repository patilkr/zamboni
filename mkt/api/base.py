import json

from django.core.exceptions import ObjectDoesNotExist

from tastypie import http
from tastypie.bundle import Bundle
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.resources import Resource, ModelResource

import commonware.log
from translations.fields import PurifiedField, TranslatedField

log = commonware.log.getLogger('z.api')


def list_url(name):
    return ('api_dispatch_list', {'resource_name': name})


def get_url(name, pk):
    return ('api_dispatch_detail', {'resource_name': name, 'pk': pk})


class Marketplace(object):
    """
    A mixin with some general Marketplace stuff.
    """

    def dispatch(self, request_type, request, **kwargs):
        # OAuth authentication uses the method in the signature. So we need
        # to store the original method used to sign the request.
        request.signed_method = request.method
        if 'HTTP_X_HTTP_METHOD_OVERRIDE' in request.META:
            request.method = request.META['HTTP_X_HTTP_METHOD_OVERRIDE']

        return (super(Marketplace, self)
                .dispatch(request_type, request, **kwargs))

    def form_errors(self, forms):
        errors = {}
        if not isinstance(forms, list):
            forms = [forms]
        for f in forms:
            if isinstance(f.errors, list):  # Cope with formsets.
                for e in f.errors:
                    errors.update(e)
                continue
            errors.update(dict(f.errors.items()))

        response = http.HttpBadRequest(json.dumps({'error_message': errors}),
                                       content_type='application/json')
        return ImmediateHttpResponse(response=response)


class MarketplaceResource(Marketplace, Resource):
    """
    Use this if you would like to expose something that is *not* a Django
    model as an API.
    """
    pass


class MarketplaceModelResource(Marketplace, ModelResource):
    """Use this if you would like to expose a Django model as an API."""

    def get_resource_uri(self, bundle_or_obj):
        # Fix until my pull request gets pulled into tastypie.
        # https://github.com/toastdriven/django-tastypie/pull/490
        kwargs = {
            'resource_name': self._meta.resource_name,
        }

        if isinstance(bundle_or_obj, Bundle):
            kwargs['pk'] = bundle_or_obj.obj.pk
        else:
            kwargs['pk'] = bundle_or_obj.pk

        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name

        return self._build_reverse_url("api_dispatch_detail", kwargs=kwargs)

    @classmethod
    def should_skip_field(cls, field):
        # We don't want to skip translated fields.
        if isinstance(field, (PurifiedField, TranslatedField)):
            return False

        return True if getattr(field, 'rel') else False

    def get_object_or_404(self, cls, **filters):
        """
        A wrapper around our more familiar get_object_or_404, for when we need
        to get access to an object that isn't covered by get_obj.
        """
        if not filters:
            raise ImmediateHttpResponse(response=http.HttpNotFound())
        try:
            return cls.objects.get(**filters)
        except (cls.DoesNotExist, cls.MultipleObjectsReturned):
            raise ImmediateHttpResponse(response=http.HttpNotFound())

    def get_by_resource_or_404(self, request, **kwargs):
        """
        A wrapper around the obj_get to just get the object.
        """
        try:
            obj = self.obj_get(request, **kwargs)
        except ObjectDoesNotExist:
            raise ImmediateHttpResponse(response=http.HttpNotFound())
        return obj


class CORSResource(object):
    """
    A mixin to provide CORS support to your API.
    """

    def method_check(self, request, allowed=None):
        """
        This is the first entry point from dispatch and a place to check CORS.

        It will set a value on the request for the middleware to pick up on
        the response and add in the headers, so that any immediate http
        responses (which are usually errors) get the headers.
        """
        request.CORS = allowed
        return super(CORSResource, self).method_check(request, allowed=allowed)
