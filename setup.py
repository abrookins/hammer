import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()

requires = ['colander']

setup(name='hammer',
      version='0.1.0',
      description='hammer',
      long_description=README,
      classifiers=[
        "Programming Language :: Python",
        ],
      author="Andrew Brookins",
      author_email='a@andrewbrookins.com',
      url='',
      keywords='json validation colander json-schema jsonschema',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires,
      test_suite="hammer",
      )

