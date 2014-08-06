# coding=utf-8
"""
Utility functions for Kata.
"""

import logging
import urllib2
import socket

from pylons import config
from lxml import etree

from ckan.lib.email_notifications import send_notification
from ckan.model import User, Package
from ckan.lib import helpers as h
from ckanext.kata import settings, helpers


log = logging.getLogger(__name__)     # pylint: disable=invalid-name


def generate_pid():
    """
    Generate a permanent Kata identifier
    """
    import datetime
    return "urn:nbn:fi:csc-kata%s" % datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")


def send_email(req):
    """
    Send access request email.

    :param user_id: user who requests access
    :param pkg_id: dataset's id
    """
    requester = User.get(req.user_id)
    pkg = Package.get(req.pkg_id)
    selrole = False
    for role in pkg.roles:
        if role.role == "admin":
            selrole = role
    if not selrole:
        return

    admin = User.get(selrole.user_id)
    admin_dict = admin.as_dict()
    admin_dict['name'] = admin.fullname if admin.fullname else admin.name

    msg = u'{a} ({b}) is requesting editing rights to the metadata in dataset\n\n{c}\n\n\
for which you are currently an administrator. Please click this \
link if you want to allow this user to edit the metadata of the dataset:\n\
{d}\n\n{a} ({b}) pyytää muokkausoikeuksia tietoaineiston\n\n{c}\n\n\
metatietoihin, joiden ylläpitäjä olet. Klikkaa linkkiä, jos haluat tämän käyttäjän \
saavan muokkausoikeudet aineiston metatietoihin:\n\
{d}\n'

    controller = 'ckanext.kata.controllers:AccessRequestController'

    requester_name = requester.fullname if requester.fullname else requester.name
    accessurl = config.get('ckan.site_url', '') + h.url_for(controller=controller, action="unlock_access", id=req.id)
    body = msg.format(a=requester_name, b=requester.email, c=pkg.title if pkg.title else pkg.name, d=accessurl)
    email_dict = {}
    email_dict["subject"] = u"Access request for dataset / pyyntö koskien tietoaineistoa %s" % pkg.title if pkg.title else pkg.name
    email_dict["body"] = body
    send_notification(admin_dict, email_dict)


def label_list_yso(tag_url):
    """
    Takes tag keyword URL and fetches the labels that link to it.

    :returns: the labels
    """

    _tagspaces = {
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'yso-meta': 'http://www.yso.fi/onto/yso-meta/2007-03-02/',
        'rdfs': "http://www.w3.org/2000/01/rdf-schema#",
        'ysa': "http://www.yso.fi/onto/ysa/",
        'skos': "http://www.w3.org/2004/02/skos/core#",
        'om': "http://www.yso.fi/onto/yso-peilaus/2007-03-02/",
        'dc': "http://purl.org/dc/elements/1.1/",
        'allars': "http://www.yso.fi/onto/allars/",
        'daml': "http://www.daml.org/2001/03/daml+oil#",
        'yso-kehitys': "http://www.yso.fi/onto/yso-kehitys/",
        'owl': "http://www.w3.org/2002/07/owl#",
        'xsd': "http://www.w3.org/2001/XMLSchema#",
        'yso': "http://www.yso.fi/onto/yso/",
    }

    labels = []
    if not tag_url.endswith("?rdf=xml"):
        tag_url += "?rdf=xml" # Small necessary bit.
    request = urllib2.Request(tag_url, headers={"Accept": "application/rdf+xml"})
    try:
        contents = urllib2.urlopen(request).read()
    except (socket.error, urllib2.HTTPError, urllib2.URLError,):
        log.debug("Failed to read tag XML.")
        return []
    try:
        xml = etree.XML(contents)
    except etree.XMLSyntaxError:
        log.debug("Tag XMl syntax error.")
        return []
    for descr in xml.xpath('/rdf:RDF/rdf:Description', namespaces=_tagspaces):
        for tag in ('yso-meta:prefLabel', 'rdfs:label', 'yso-meta:altLabel',):
            nodes = descr.xpath('./%s' % tag, namespaces=_tagspaces)
            for node in nodes:
                text = node.text.strip() if node.text else ''
                if text:
                    labels.append(text)
    return labels


def resource_to_dataset(data_dict):
    '''
    Move some fields from resources to dataset. Used for viewing a dataset.

    We need field conversions to make sure the whole 'resources' key in datadict doesn't get overwritten when
    modifying the dataset in WUI. That would drop all manually added resources if resources was already present.

    :param data_dict: the data dictionary
    :returns: the modified data dictionary (resources handled)
    '''
    resource = None

    if 'resources' in data_dict:
        for i in range(len(data_dict['resources'])):
            if data_dict['resources'][i].get('resource_type', None) == settings.RESOURCE_TYPE_DATASET:
                # UI can't handle multiple instances of 'dataset' resources, so now use only the first.
                resource = data_dict['resources'][i]
                break

    if not resource and 'id' in data_dict:
        log.debug('Dataset without a dataset resource: %s', data_dict['id'])
        return data_dict

    if resource:
        data_dict.update({
            'direct_download_URL': resource.get('url', u''),
            'checksum': resource.get('hash', u''),
            'mimetype': resource.get('mimetype', u''),
            'algorithm': resource.get('algorithm', u''),
        })

    return data_dict


def dataset_to_resource(data_dict):
    '''
    Move some fields from dataset to resources. Used for saving to DB.

    Now finds the first 'dataset' resource and updates it. Not sure how this should be handled with multiple
    'dataset' resources. Maybe just remove all of them and add new ones as they all are expected to be present
    when updating a dataset.

    :param data_dict: the data dictionary
    :returns: the modified data dictionary (resources handled)
    '''
    resource_index = None

    if 'resources' in data_dict:
        for i in range(len(data_dict['resources'])):
            if data_dict['resources'][i].get('resource_type', None) == settings.RESOURCE_TYPE_DATASET:
                # Use the first 'dataset' resource.
                resource_index = i
                break
    else:
        data_dict['resources'] = [None]
        resource_index = 0

    if data_dict.get('availability') != 'direct_download':
        data_dict['direct_download_URL'] = None
        if resource_index is not None:
            # Empty the found 'dataset' resource if availability is not 'direct_download' to get rid of it's URL
            # which is the used as the direct_download_URL.
            data_dict['resources'][resource_index] = {}

    if resource_index is None:
        # Resources present, but no 'dataset' resource found. Add resource to the beginning of list.
        data_dict['resources'].insert(0, {})
        resource_index = 0

    data_dict['resources'][resource_index] = {
        'url': data_dict.get('direct_download_URL', settings.DATASET_URL_UNKNOWN),
        'hash': data_dict.get('checksum', u''),
        'mimetype': data_dict.get('mimetype', u''),
        'algorithm': data_dict.get('algorithm', u''),
        'resource_type': settings.RESOURCE_TYPE_DATASET,
    }

    return data_dict


def hide_sensitive_fields(pkg_dict1):
    '''
    Hide fields that contain sensitive data. Modifies input dict directly.

    :param pkg_dict1: data dictionary from package_show
    :returns: the modified data dictionary
    '''

    # pkg_dict1['maintainer_email'] = _('Not authorized to see this information')
    # pkg_dict1['project_funding'] = _('Not authorized to see this information')
    funders = helpers.get_funders(pkg_dict1)
    for fun in funders:
        fun.pop('fundingid', None)

    for con in pkg_dict1.get('contact', []):
        # String 'hidden' triggers the link for contact form, see metadata_info.html
        con['email'] = 'hidden'

    return pkg_dict1


def get_field_titles(_):
    '''
    Get correctly translated titles for search fields

    :param _: gettext translator
    :returns: dict of titles for fields
    '''

    translated_field_titles = {}

    for k, v in settings._FIELD_TITLES.iteritems():
        translated_field_titles[k] = _(v)

    return translated_field_titles


def get_field_title(key, _):
    '''
    Get correctly translated title for one search field

    :param _: gettext translator
    :returns: dict of titles for fields
    '''

    return _(settings._FIELD_TITLES[key])