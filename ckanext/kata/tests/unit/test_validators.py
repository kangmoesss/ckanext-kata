# coding: utf-8
#
# pylint: disable=no-self-use, missing-docstring, too-many-public-methods, invalid-name

"""
Test classes for Kata's validators.
"""

import copy
from unittest import TestCase
from collections import defaultdict

from ckanext.kata.validators import validate_kata_date, check_project, \
    check_project_dis, validate_email, validate_phonenum, \
    validate_discipline, validate_spatial, validate_algorithm, \
    validate_mimetype, validate_general, validate_kata_date_relaxed
from ckan.lib.navl.dictization_functions import Invalid, flatten_dict
from ckanext.kata.converters import remove_disabled_languages, checkbox_to_boolean, convert_languages
from ckanext.kata import settings

class TestValidators(TestCase):
    """Tests for Kata validators."""

    @classmethod
    def setup_class(cls):
        """Set up tests."""

        # TODO: Get a new flattened data_dict

        cls.test_data = {('__extras',): {'_ckan_phase': u'',
                'evdescr': [],
                'evwhen': [],
                'evwho': [],
                'groups': [],
                'pkg_name': u''},
            ('availability',): u'contact',
            ('access_application_URL',): u'',
            ('access_request_URL',): u'',
            ('algorithm',): u'',
            ('author', 0, 'value'): u'dada',
            ('checksum',): u'',
            ('contact_URL',): u'http://google.com',
            ('discipline',): u'',
            ('evtype', 0, 'value'): u'collection',
            ('extras',): [{'key': 'funder', 'value': u''},
                {'key': 'discipline', 'value': u''},
                {'key': 'maintainer', 'value': u'dada'},
                {'key': 'mimetype', 'value': u''},
                {'key': 'project_funding', 'value': u''},
                {'key': 'project_homepage', 'value': u''},
                {'key': 'owner', 'value': u'dada'},
                {'key': 'temporal_coverage_begin', 'value': u''},
                {'key': 'direct_download_URL', 'value': u''},
                {'key': 'phone', 'value': u'+35805050505'},
                {'key': 'license_URL', 'value': u'dada'},
                {'key': 'geographic_coverage', 'value': u''},
                {'key': 'access', 'value': u'contact'},
                {'key': 'algorithm', 'value': u''},
                {'key': 'langdis', 'value': u'True'},
                {'key': 'access_application_URL', 'value': u''},
                {'key': 'contact_URL', 'value': u'http://google.com'},
                {'key': 'project_name', 'value': u''},
                {'key': 'checksum', 'value': u''},
                {'key': 'temporal_coverage_end', 'value': u''},
                {'key': 'projdis', 'value': u'True'},
                {'key': 'language', 'value': u''}],
            ('mimetype',): u'',
            ('project_funder',): u'',
            ('geographic_coverage',): u'',
            ('langdis',): u'False',
            ('language',): u'swe',
            ('license_URL',): u'dada',
            ('license_id',): u'',
            ('log_message',): u'',
            ('name',): u'',
            ('notes',): u'',
            ('organization', 0, 'value'): u'dada',
            ('owner',): u'dada',
            ('phone',): u'+35805050505',
            ('maintainer_email',): u'kata.selenium@gmail.com',
            ('projdis',): u'True',
            ('project_funding',): u'',
            ('project_homepage',): u'',
            ('project_name',): u'',
            ('maintainer',): u'dada',
            ('save',): u'finish',
            ('tag_string',): u'dada',
            ('temporal_coverage_begin',): u'',
            ('temporal_coverage_end',): u'',
            ('title', 0, 'lang'): u'sv',
            ('title', 0, 'value'): u'dada',
            ('type',): None,
            ('version',): u'2013-08-14T10:37:09Z',
            ('version_PID',): u''}

    def test_validate_kata_date_valid(self):
        errors = defaultdict(list)
        validate_kata_date('date', {'date': '2012-12-31T13:12:11'}, errors, None)
        assert len(errors) == 0

    def test_validate_kata_date_invalid(self):
        errors = defaultdict(list)
        validate_kata_date('date', {'date': '20xx-xx-31T13:12:11'}, errors, None)
        assert len(errors) > 0

    def test_validate_kata_date_invalid_2(self):
        errors = defaultdict(list)
        validate_kata_date('date', {'date': '2013-02-29T13:12:11'}, errors, None)
        assert len(errors) > 0

    def test_validate_kata_date_relaxed_valid(self):
        errors = defaultdict(list)
        validate_kata_date_relaxed('date', {'date': '2012-12-31T13:12:11'}, errors, None)
        assert len(errors) == 0

    def test_validate_kata_date_relaxed_valid_2(self):
        errors = defaultdict(list)
        validate_kata_date_relaxed('date', {'date': '2012-12'}, errors, None)
        assert len(errors) == 0

    def test_validate_kata_date_relaxed_valid_3(self):
        errors = defaultdict(list)
        validate_kata_date_relaxed('date', {'date': '2012-12-31'}, errors, None)
        assert len(errors) == 0

    def test_validate_kata_date_relaxed_invalid(self):
        errors = defaultdict(list)
        validate_kata_date_relaxed('date', {'date': '2001-12-45'}, errors, None)
        assert len(errors) > 0

    def test_validate_kata_date_relaxed_invalid_2(self):
        errors = defaultdict(list)
        validate_kata_date_relaxed('date', {'date': '2013-02-99T13:12:11'}, errors, None)
        assert len(errors) > 0


    def test_validate_language_valid(self):
        errors = defaultdict(list)
        convert_languages(('language',), self.test_data, errors, None)
        assert len(errors) == 0

    def test_remove_disabled_languages_valid(self):
        errors = defaultdict(list)
        remove_disabled_languages(('language',), self.test_data, errors, None)
        assert len(errors) == 0

    def test_validate_language_valid_2(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('language',)] = u''
        dada[('langdis',)] = 'True'

        convert_languages(('language',), dada, errors, None)
        assert len(errors) == 0

        remove_disabled_languages(('language',), dada, errors, None)
        assert len(errors) == 0

    def test_validate_language_valid_3(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('language',)] = u'fin, swe, eng, isl'
        dada[('langdis',)] = 'False'

        convert_languages(('language',), dada, errors, None)
        assert len(errors) == 0

        remove_disabled_languages(('language',), dada, errors, None)
        assert len(errors) == 0
        assert dada[('language',)] == u'fin, swe, eng, isl'

    def test_validate_language_delete(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('language',)] = u'fin, swe, eng, ita'
        dada[('langdis',)] = 'True'

        convert_languages(('language',), dada, errors, None)
        assert len(errors) == 0

        remove_disabled_languages(('language',), dada, errors, None)
        assert len(errors) == 0
        assert dada[('language',)] == u''

    def test_validate_language_invalid(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('language',)] = u'aa, ab, ac, ad, ae, af'
        dada[('langdis',)] = 'False'

        convert_languages(('language',), dada, errors, None)
        assert len(errors) == 1

    def test_validate_language_invalid_2(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('language',)] = u''
        dada[('langdis',)] = 'False'

        convert_languages(('language',), dada, errors, None)
        remove_disabled_languages(('language',), dada, errors, None)
        assert len(errors) == 1

    def test_validate_language_invalid_3(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('language',)] = u'finglish, sv, en'
        dada[('langdis',)] = 'True'

        convert_languages(('language',), dada, errors, None)
        assert len(errors) == 1

    def test_project_valid(self):
        errors = defaultdict(list)
        dada = copy.deepcopy(self.test_data)
        dada[('projdis',)] = 'False'
        dada[('funder',)] = u'funder'
        dada[('project_name',)] = u'project name'
        dada[('project_funding',)] = u'project_funding'
        dada[('project_homepage',)] = u'www.google.fi'

        check_project_dis(('project_name',),
                          dada, errors, None)
        assert len(errors) == 0
        check_project_dis(('funder',),
                          dada, errors, None)
        assert len(errors) == 0
        check_project_dis(('project_funding',),
                          dada, errors, None)
        assert len(errors) == 0
        check_project_dis(('project_homepage',),
                          dada, errors, None)
        assert len(errors) == 0

    def test_project_invalid(self):
        errors = defaultdict(list)
        dada = copy.deepcopy(self.test_data)
        dada[('projdis',)] = 'False'
        dada[('funder',)] = u''
        dada[('project_name',)] = u'project name'
        dada[('project_funding',)] = u'project_funding'
        dada[('project_homepage',)] = u'www.google.fi'

        check_project_dis(('project_name',),
                          dada, errors, None)
        assert len(errors) == 0
        check_project_dis(('funder',),
                          dada, errors, None)
        assert len(errors) > 0

    def test_project_notgiven(self):
        errors = defaultdict(list)
        dada = copy.deepcopy(self.test_data)
        dada[('projdis',)] = 'True'
        dada[('project_name',)] = u'project name'
        check_project(('project_name',),
                      dada, errors, None)
        print errors
        assert len(errors) > 0

    def test_validate_email_valid(self):
        errors = defaultdict(list)

        validate_email(('maintainer_email',), self.test_data, errors, None)

        assert len(errors) == 0

    def test_validate_email_valid_2(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('maintainer_email',)] = u'a.b.c.d@e.com'

        validate_email(('maintainer_email',), dada, errors, None)

        assert len(errors) == 0

    def test_validate_email_invalid(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('maintainer_email',)] = u'a.b.c.d'

        validate_email(('maintainer_email',), dada, errors, None)

        assert len(errors) == 1

    def test_validate_email_invalid_2(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('maintainer_email',)] = u'a.b@com'

        validate_email(('maintainer_email',), dada, errors, None)

        assert len(errors) == 1

    def test_validate_phonenum_valid(self):
        errors = defaultdict(list)

        validate_phonenum(('phone',), self.test_data, errors, None)

        assert len(errors) == 0

    def test_validate_phonenum_invalid(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('phone',)] = u'123_notgood_456'

        validate_phonenum(('phone',), dada, errors, None)

        assert len(errors) == 1

    def test_general_validator_invalid(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('project_homepage',)] = u'http://www.<asdf123456>'

        validate_general(('project_homepage',), dada, errors, None)
        assert len(errors) == 1

    def test_validate_discipline(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('discipline',)] = u'Matematiikka'

        validate_discipline(('discipline',), dada, errors, None)
        assert len(errors) == 0

        del dada[('discipline',)]
        validate_discipline(('discipline',), dada, errors, None)
        assert len(errors) == 0

        dada[('discipline',)] = u'Matematiikka (Logiikka!)'
        self.assertRaises(Invalid, validate_discipline, ('discipline',), dada, errors, None)

    def test_validate_spatial(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('geographic_coverage',)] = u'Uusimaa (laani)'

        validate_spatial(('geographic_coverage',), dada, errors, None)
        assert len(errors) == 0

        del dada[('geographic_coverage',)]
        validate_spatial(('geographic_coverage',), dada, errors, None)
        assert len(errors) == 0

        dada[('geographic_coverage',)] = u'Uusimaa ([]!)'
        self.assertRaises(Invalid, validate_spatial, ('geographic_coverage',), dada, errors, None)

    def test_checkbox_to_boolean(self):
        errors = defaultdict(list)

        dada = copy.deepcopy(self.test_data)
        dada[('langdis',)] = u'True'
        checkbox_to_boolean(('langdis',), dada, errors, None)
        assert dada[('langdis',)] == u'True'

        dada[('langdis',)] = u'False'
        checkbox_to_boolean(('langdis',), dada, errors, None)
        assert dada[('langdis',)] == u'False'

        dada[('langdis',)] = u'on'
        checkbox_to_boolean(('langdis',), dada, errors, None)
        assert dada[('langdis',)] == u'True'

        dada[('langdis',)] = u''
        checkbox_to_boolean(('langdis',), dada, errors, None)
        assert dada[('langdis',)] == u'False'


class TestResourceValidators(TestCase):
    '''
    Test validators for resources
    '''

    @classmethod
    def setup_class(cls):
        '''
        Using the resource's format for resource validator tests
        '''
        cls.test_data = {
            'resources': [{
                'url' : u'http://www.csc.fi',
                'algorithm': u'MD5',
                'hash': u'f60e586509d99944e2d62f31979a802f',
                'mimetype': u'application/pdf',
                'resource_type' : settings.RESOURCE_TYPE_DATASET,
                }]
            }

    def test_validate_mimetype_valid(self):
        errors = defaultdict(list)

        data_dict = copy.deepcopy(self.test_data)
        data_dict['resources'][0]['format'] = u'vnd.3gpp2.bcmcsinfo+xml/'
        # flatten dict (or change test_data to flattened form?)
        data = flatten_dict(data_dict)
        try:
            validate_mimetype(('resources', 0, 'mimetype',), data, errors, None)
        except Invalid:
            raise AssertionError('Mimetype raised exception, it should not')

    def test_validate_mimetype_invalid(self):
        errors = defaultdict(list)

        data_dict = copy.deepcopy(self.test_data)
        data_dict['resources'][0]['format'] = u'application/pdf><'
        data = flatten_dict(data_dict)

        self.assertRaises(Invalid, validate_mimetype, ('resources', 0, 'format',), data, errors, None)

    def test_validate_algorithm_valid(self):
        errors = defaultdict(list)

        data_dict = copy.deepcopy(self.test_data)
        data_dict['resources'][0]['algorithm'] = u'RadioGatún-1216'
        data = flatten_dict(data_dict)

        try:
            validate_algorithm(('resources', 0, 'algorithm',), data, errors, None)
        except Invalid:
            raise AssertionError('Algorithm raised exception, it should not')

    def test_validate_algorithm_invalid(self):
        errors = defaultdict(list)

        data_dict = copy.deepcopy(self.test_data)
        data_dict['resources'][0]['algorithm'] = u'RadioGatún-1216!>'
        data = flatten_dict(data_dict)

        self.assertRaises(Invalid, validate_algorithm, ('resources', 0, 'algorithm',), data, errors, None)

