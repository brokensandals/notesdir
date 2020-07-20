Templating
==========

If you routinely create notes that follow a certain pattern, you might want to make a template for them.
Notesdir lets you do this using `Mako <https://www.makotemplates.org/>`__, a templating language that supports embedded Python code.

Configuration
-------------

No configuration is necessary, but for convenience, you'll probably want to specify the folder(s) you keep your templates in.
That way you can refer to them by name instead of by their full path.

Set :attr:`notesdir.conf.NotesdirConf.template_globs` in your ``~/notesdir.conf.py``:

.. code-block:: python

   conf.template_globs = {'/notes/templates/*.mako'}

Writing templates
-----------------

Every month I create a new Markdown file for tracking that month's goals.
I want the template to fill in the creation date, give the note a title and filename that show it's for next month, put it in the right directory, and include some standard tags and todo items.

.. code-block:: text

   <%
     from datetime import datetime, timezone
     from pathlib import Path
     # Get the current time in the system timezone
     created = datetime.now(timezone.utc).astimezone()
     # Build a string like "2020-04" for whatever next month is
     yearmonth = created.replace(day=1)
     yearmonth = yearmonth.replace(year=yearmonth.year+1, month=1) if yearmonth.month == 12 else yearmonth.replace(month=yearmonth.month+1)
     yearmonth = yearmonth.strftime('%Y-%m')
     # Set where the new file should be written.
     # This is optional. You can also set the destination on the command line.
     # In this case, I'm setting a path that's relative to where the template itself is stored,
     # using the template_path variable notesdir provides.
     directives.dest = str(Path(template_path).parent.parent.joinpath('active', f'goals-{yearmonth}.md'))
   %>\
   ---
   created: ${created.isoformat()}
   title: Goals ${yearmonth}
   keywords:
   - monthly-goals
   - journal
   ...

   <%text>
   # Must do

   ## Stay alive

   - eat food
   - sleep
   </%text>\

The ``directives`` variable is an instance of :class:`notesdir.models.TemplateDirectives` which notesdir uses for passing data in and out of the template.

In the example above, notice the ``<%text>`` element: this tells Mako not to process the text inside it.
This prevents the Markdown ``##`` header syntax from being misinterpreted as a comment.

Using templates
---------------

Given the configuration above, if I store the example template in ``/notes/templates/goals.md.mako``, I can run this to create a new file from the template:

.. code-block:: bash

   notesdir new goals

In the example above, the template sets its own destination; in this case, the result would be something like ``/notes/active/goals-2020-08.md``.

But in other cases you may wish to specify the destination on the command-line:

.. code-block:: bash

   notesdir new template_name_or_path destination_file_path
