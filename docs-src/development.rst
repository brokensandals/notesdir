Development
===========

Setup
-----

1. Install python3 and pip
2. Clone the repo from github
3. Create a virtual environment:

   .. code-block:: bash

      cd notesdir
      python3 -m venv venv
      source venv/bin/active

4. Install runtime and development dependencies:

   .. code-block:: bash

      pip install .
      pip install -r requirements-dev.txt

Then you should be ready to go.

Running
-------

To run unit tests:

.. code-block:: bash

   PYTHONPATH=src pytest

(Overriding PYTHONPATH as shown ensures the tests run against the code in the src/ directory rather than the installed copy of the package.)

If you use PyCharm, it should be straightforward to run the tests in it too, using a pytest run configuration.
Just make sure to mark ``src`` as a source directory in Project Structure.

To run the CLI:

.. code-block:: bash

   PYTHONPATH=src python -m notesdir --help

Building the docs
-----------------

.. code-block:: bash

   cd docs-src
   make clean && make html

Then open the file ``_build/html/index.html``.
