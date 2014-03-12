from setuptools import setup, find_packages
import sys, os

version = '0.333'

setup(
    name='ckanext-kata',
    version=version,
    description="KATA extensions for CKAN",
    long_description="""Provides modified Add Dataset (package) page and other modifications. This extension contains also jQuery files, custom css (eg. kata.css) and several templates are overwritten from basic CKAN to provide the Kata/TTA looks.""",
    classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    keywords='',
    author='CSC - IT Center for Science Ltd.',
    author_email='kata-project@postit.csc.fi',
    url='https://github.com/kata-csc/ckanext-kata',
    license='AGPL',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    namespace_packages=['ckanext', 'ckanext.kata'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        # -*- Extra requirements: -*-
        'rdflib',
        'iso8601 >= 0.1.5',
        'pycountry',
    ],
    package_data={'ckan': [
        'i18n/*/LC_MESSAGES/*.mo',
        ]
    },
    message_extractors = {
        'ckanext': [
                        ('**.py', 'python', None),#
                        ('kata/theme/templates/package/**.html', 'ckan', None),
                        ('kata/theme/templates/privacypolicy.html', 'ckan', None),
                        ('kata/theme/templates/header.html', 'ckan', None),
                        ('kata/theme/templates/footer.html', 'ckan', None),
                        ('kata/theme/templates/kata/**.html', 'ckan', None),
                        ('kata/theme/templates/group/**.html', 'ckan', None),
                        ('kata/theme/templates/datamining/**.html', 'ckan', None),
                        ('kata/theme/templates/revision/**.html', 'ckan', None),
                        ('kata/theme/templates/contact/**.html', 'ckan', None),
                        ('kata/theme/templates/snippets/**.html', 'ckan', None),
                        ('kata/theme/templates/home/**.html', 'ckan', None),
                        
                        ],
    },
    entry_points=\
    """
    [ckan.plugins]
    # Add plugins here, eg
    kata=ckanext.kata.plugin:KataPlugin
    kata_metadata=ckanext.kata.plugin:KataMetadata
    [paste.paster_command]
    katacmd = ckanext.kata.commands.kata:Kata
    """,

)
