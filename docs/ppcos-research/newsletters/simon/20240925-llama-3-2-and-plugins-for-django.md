# Llama 3.2 and plugins for Django

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-09-25T23:22:57.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/llama-32-and-plugins-for-django

In this newsletter:
Llama 3.2
DJP: A plugin system for Django
Notes on using LLMs for code
Things I've learned serving on the board of the Python Software Foundation
Plus 22 links and 12 quotations and 1 TIL
Link: Llama 3.2 [ https://substack.com/redirect/2a334982-3333-436b-9667-9861c0bd3056?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
In further evidence that AI labs are terrible at naming things, Llama 3.2 is a huge upgrade to the Llama 3 series - they've released their first multi-modal vision models!
Today, we’re releasing Llama 3.2, which includes small and medium-sized vision LLMs (11B and 90B), and lightweight, text-only models (1B and 3B) that fit onto edge and mobile devices, including pre-trained and instruction-tuned versions.
The 1B and 3B text-only models are exciting too, with a 128,000 token context length and optimized for edge devices (Qualcomm and MediaTek hardware get called out specifically).
Meta partnered directly with Ollama to help with distribution, here's the Ollama blog post [ https://substack.com/redirect/d3981e65-8fa1-4052-83ed-e39927130d6f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. They only support the two smaller text-only models at the moment - this command will get the 3B model (2GB):
ollama run llama3.2
And for the 1B model (a 1.3GB download):
ollama run llama3.2:1b
I had to first upgrade my Ollama by clicking on the icon in my macOS task tray and selecting "Restart to update".
The two vision models are coming to Ollama "very soon".
Once you have fetched the Ollama model you can access it from my LLM [ https://substack.com/redirect/8553e34e-2554-4df3-b030-59b803cda48f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] command-line tool like this:
pipx install llm
llm install llm-ollama
llm chat -m llama3.2:1b
I tried running my djp codebase [ https://substack.com/redirect/7fa918dd-fe56-4b2c-bb8b-7b2ff8b3ec8b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] through that tiny 1B model just now and got a surprisingly good result [ https://substack.com/redirect/e2b1a81f-fe6a-406b-b059-d1c6631af171?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - by no means comprehensive, but way better than I would ever expect from a model of that size:
files-to-prompt **/*.py -c | llm -m llama3.2:1b --system 'describe this code'
Here's a portion of the output:
The first section defines several test functions using the @djp.hookimpldecorator from the djp library. These hook implementations allow you to intercept and manipulate Django's behavior.
test_middleware_order: This function checks that the middleware order is correct by comparing the MIDDLEWARE setting with a predefined list.
test_middleware: This function tests various aspects of middleware:
It retrieves the response from the URL /from-plugin/ using the Client object, which simulates a request to this view.
It checks that certain values are present in the response:
X-DJP-Middleware-After
X-DJP-Middleware
X-DJP-Middleware-Before [...]
I found the GGUF file that had been downloaded by Ollama in my ~/.ollama/models/blobsdirectory. The following command let me run that model directly in LLM using the llm-gguf [ https://substack.com/redirect/fc0e6bf8-b720-43c1-9fde-8c50d57c3edc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]plugin:
llm install llm-gguf
llm gguf register-model ~/.ollama/models/blobs/sha256-74701a8c35f6c8d9a4b91f3f3497643001d63e0c7a84e085bed452548fa88d45 -a llama321b
llm chat -m llama321b
Meta themselves claim impressive performance against other existing models:
Our evaluation suggests that the Llama 3.2 vision models are competitive with leading foundation models, Claude 3 Haiku and GPT4o-mini on image recognition and a range of visual understanding tasks. The 3B model outperforms the Gemma 2 2.6B and Phi 3.5-mini models on tasks such as following instructions, summarization, prompt rewriting, and tool-use, while the 1B is competitive with Gemma.
Here's the Llama 3.2 collection [ https://substack.com/redirect/5fdf5f31-3833-441a-a699-279d75fa27d4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Hugging Face. You need to accept the new Llama 3.2 Community License Agreement there in order to download those models.
You can try the four new models out via the Chatbot Arena [ https://substack.com/redirect/d8f01bee-a3f1-4908-9857-f3d7c1128386?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - navigate to "Direct Chat" there and select them from the dropdown menu. You can upload images directly to the chat there to try out the vision features.
DJP: A plugin system for Django [ https://substack.com/redirect/6cdcf35a-1784-4795-bd9f-ec4fc0618262?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-25
DJP [ https://substack.com/redirect/493b9761-3fe9-4560-be0c-25a0bcfd9e7f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a new plugin mechanism for Django, built on top of Pluggy [ https://substack.com/redirect/7157bd7b-02db-4741-8018-55289d591d47?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I announced the first version of DJP during my talk yesterday at DjangoCon US 2024, How to design and implement extensible software with plugins [ https://substack.com/redirect/dc688db4-9f5e-43c1-8839-b54d34551cf5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I'll post a full write-up of that talk once the video becomes available - this post describes DJP and how to use what I've built so far.
Why plugins? [ https://substack.com/redirect/0eae68da-a504-419c-9f82-67275cf0f1b3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Setting up DJP [ https://substack.com/redirect/a2967939-762a-4ada-abf1-e66f98b195be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
django-plugin-django-header [ https://substack.com/redirect/c075c6df-d4f4-4876-9c1e-7bfacfcc4d3b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
django-plugin-blog [ https://substack.com/redirect/9b871e64-f214-4583-afc0-0c58d1f59ab1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
django-plugin-database-url [ https://substack.com/redirect/c3ceddb1-7cf1-4f03-9f47-36d460f08101?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Writing a plugin [ https://substack.com/redirect/d84e05ba-465f-49e5-ba6e-9f9e0b1b3900?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Writing tests for plugins [ https://substack.com/redirect/58463ca4-6102-498c-bd7c-707b1596c78e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Why call it DJP? [ https://substack.com/redirect/ebdc7c3f-febe-49c4-95a2-26e41ce5cb92?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
What's next for DJP? [ https://substack.com/redirect/33258c50-c102-43e0-b40d-7c26e95409b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Why plugins?
Django already has a thriving ecosystem of third-party apps and extensions. What can a plugin system add here?
If you've ever installed a Django extension - such as django-debug-toolbar [ https://substack.com/redirect/dbf06c90-b3cf-47a2-a9c0-077fde86e250?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] or django-extensions [ https://substack.com/redirect/c5b8c09f-a6e9-42f4-a5d4-8f6de3bd3ba0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - you'll be familiar with the process. You pip install the package, then add it to your list of INSTALLED_APPS in settings.py - and often configure other picees, like adding something to MIDDLEWARE or updating your urls.py with new URL patterns.
This isn't exactly a huge burden, but it's added friction. It's also the exact kind of thing plugin systems are designed to solve.
DJP addresses this. You configure DJP just once, and then any additional DJP-enabled plugins you pip install can automatically register configure themselves within your Django project.
Setting up DJP
There are three steps to adding DJP to an existing Django project:
pip install djp - or add it to your requirements.txt or similar.
Modify your settings.py to add these two lines:
# Can be at the start of the file:
import djp

# This MUST be the last line:
djp.settings(globals)
Modify your urls.py to contain the following:
import djp

urlpatterns = [
# Your existing URL patterns
] + djp.urlpatterns
That's everything. The djp.settings(globals) line is a little bit of magic - it gives djp an opportunity to make any changes it likes to your configured settings.
You can see what that does here [ https://substack.com/redirect/91b70ae3-19ca-4955-be7b-1a8d7d5d1052?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Short version: it adds "djp" and any other apps from plugins to INSTALLED_APPS, modifies MIDDLEWARE for any plugins that need to do that and gives plugins a chance to modify any other settings they need to.
One of my personal rules of plugin system design is that you should never ship a plugin hook (a customization point) without releasing at least one plugin that uses it. This validates the design and provides executable documentation in the form of working code.
I've released three plugins for DJP so far.
django-plugin-django-header
django-plugin-django-header [ https://substack.com/redirect/ec4d7c84-7a6f-492d-9cf1-470e8a94b857?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a very simple initial example. It registers a Django middleware class [ https://substack.com/redirect/5448e474-d21a-478d-baa4-e652b11a793c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that adds a Django-Composition: HTTP header to every response with the name of a random Composition by Django Reinhardt [ https://substack.com/redirect/4fadee60-9da7-4efb-a4ae-5ba47d222eef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (thanks,Wikipedia [ https://substack.com/redirect/30cc421b-de2f-476b-b694-71b9a7d672ac?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
pip install django-plugin-django-header
Then try it out with curl:
curl -I http://localhost:8000/
You should get back something like this:
...
Django-Composition: Nuages
...

I'm running this on my blog right now! Try this command to see it in action:
curl -I https://simonwillison.net/
The plugin is very simple. Its __init__.py [ https://substack.com/redirect/ebb2c443-6d9c-4ffc-b92f-5f59209691b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]registers middleware like this:
import djp

@djp.hookimpl
def middleware:
return [
"django_plugin_django_header.middleware.DjangoHeaderMiddleware"
]
That string references the middleware class in this file [ https://substack.com/redirect/3c3a9bcf-69db-440a-a6c6-fdc1f3f55f43?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
django-plugin-blog
django-plugin-blog [ https://substack.com/redirect/6a366683-1e7c-451f-a6b1-7f9a82b65f58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a much bigger example. It implements a full blog system for your Django application, with bundled models and templates and views and a URL configuration.
You'll need to have configured auth and the Django admin already (those already there by default in the django-admin startprojecttemplate). Now install the plugin:
pip install django-plugin-blog
And run migrations to create the new database tables:
python manage.py migrate
That's all you need to do. Navigating to /blog/will present the index page of the blog, including a link to a working Atom feed.
You can add entries and tags through the Django admin (configured for you by the plugin) and those will show up on /blog/, get their own URLs at /blog/2024// and be included in the Atom feed, the /blog/archive/ list and the /blog/2024/ year-based index too.
The default design is very basic, but you can customize that by providing your own base template or providing custom templates for each of the pages. There are details on the templates in the README [ https://substack.com/redirect/6a366683-1e7c-451f-a6b1-7f9a82b65f58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The blog implementation is directly adapted from my Building a blog in Django [ https://substack.com/redirect/3ac45072-a032-4e5b-9b94-09070977914d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] TIL.
The primary goal of this plugin is to demonstrate what a plugin with views, templates, models and a URL configuration looks like. Here's the full __init__.py for the plugin [ https://substack.com/redirect/91fe9ab9-9b2b-46db-81f2-057a1a50a3a9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
from django.urls import path
from django.conf import settings
import djp

@djp.hookimpl
def installed_apps:
return ["django_plugin_blog"]

@djp.hookimpl
def urlpatterns:
from .views import index, entry, year, archive, tag, BlogFeed

blog = getattr(settings, "DJANGO_PLUGIN_BLOG_URL_PREFIX", None) or "blog"
return [
path(f"{blog}/", index, name="django_plugin_blog_index"),
path(f"{blog}///", entry, name="django_plugin_blog_entry"),
path(f"{blog}/archive/", archive, name="django_plugin_blog_archive"),
path(f"{blog}//", year, name="django_plugin_blog_year"),
path(f"{blog}/tag//", tag, name="django_plugin_blog_tag"),
path(f"{blog}/feed/", BlogFeed, name="django_plugin_blog_feed"),
]
It still only needs to implement two hooks: one to add django_plugin_blog to the INSTALLED_APPS list and another to add the necessary URL patterns to the project.
The from .views import ... line is nested inside the urlpatterns hook because I was hitting circular import issues with those imports at the top of the module.
django-plugin-database-url
django-plugin-database-url [ https://substack.com/redirect/8932654a-721e-40f7-8f93-0d9a87d541ba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is the smallest of my example plugins. It exists mainly to exercise the settings plugin hook, which allows plugins to further manipulate settings in any way they like.
Quoting the README [ https://substack.com/redirect/fcaa5485-862c-40ed-9eb9-f0465a9fc75f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Once installed, any DATABASE_URLenvironment variable will be automatically used to configure your Django database setting, using dj-database-url [ https://substack.com/redirect/25e1befd-e4bc-424b-bdd3-d7b7cfdc9d95?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Here's the full implementation [ https://substack.com/redirect/211164c0-786e-4349-b4df-546979089c97?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of that plugin, most of which is copied straight from the dj-database-url documentation [ https://substack.com/redirect/948160ea-3a9b-4b5f-b862-c6e82d2736cd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
import djp
import dj_database_url

@djp.hookimpl
def settings(current_settings):
current_settings["DATABASES"]["default"] = dj_database_url.config(
conn_max_age=600,
conn_health_checks=True,
)
If DJP gains tration, I expect that a lot of plugins will look like this - thin wrappers around existing libraries where the only added value is that they configure those libraries automatically once the plugin is installed.
Writing a plugin
A plugin is a Python package bundling a module that implements one or more of the DJP plugin hooks [ https://substack.com/redirect/eb5dfbfa-2813-454c-9853-8de79e655960?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
As I've shown above, the Python code for plugins can be very short. The larger challenge is correctly packaging and distributing the plugin - plugins are discovered using Entry Points [ https://substack.com/redirect/4ba85ea8-2d96-4b6f-81f7-822e51c8cb32?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which are defined in a pyproject.tomlfile, and you need to get those exactly right for your plugin to be discovered.
DJP includes documentation on creating a plugin [ https://substack.com/redirect/61958feb-7f49-4b84-9cfa-001a80de3980?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], but to make it as frictionless as possible I've released a new django-plugin cookiecutter template [ https://substack.com/redirect/03365b99-4f1a-4918-a25d-5d4c2153bdf2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
This means you can start a new plugin like this:
pip install cookiecutter
cookiecutter gh:simonw/django-plugin
Then answer the questions:
[1/6] plugin_name : django-plugin-example
[2/6] description : A simple example plugin
[3/6] hyphenated (django-plugin-example):
[4/6] underscored (django_plugin_example):
[5/6] github_username : simonw
[6/6] author_name : Simon Willison
And you'l get a django-plugin-example directory with a fully configured plugin ready to be published to PyPI.
The template includes a .github/workflowsdirectory with actions that can run tests, and an action that publishes your plugin to PyPI any time you create a new release on GitHub.
I've used that pattern myself for hundreds of plugin projects for Datasette [ https://substack.com/redirect/e66e9e9a-0ccd-4190-a24e-1815530ec84d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and LLM [ https://substack.com/redirect/8553e34e-2554-4df3-b030-59b803cda48f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], so I'm confident this is an effective way to release plugins.
The workflows use PyPI's Trusted Publishers [ https://substack.com/redirect/4e8d6d84-b60c-45b9-b30c-c5f76b3c2bb5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]mechanism (see my TIL [ https://substack.com/redirect/b01544fb-753c-4519-bbfb-942d6ff3910a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), which means you don't need to worry about API keys or PyPI credentials - configure the GitHub repo once using the PyPI UI and everything should just work.
Writing tests for plugins
Writing tests for plugins can be a little tricky, especially if they need to spin up a full Django environment in order to run the tests.
I previously published a TIL about that [ https://substack.com/redirect/72db58ab-1ec6-4398-b1a3-ff34918c4b3a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], showing how to have tests with their own tests/test_project project that can be used by pytest-django [ https://substack.com/redirect/a234b05c-a08c-49f8-be26-afd93ae48179?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I've baked that pattern into the simon/django-plugin cookiecutter template as well, plus a single default test which checks that a hit to the / index page returns a 200 status code - still a valuable default test since it confirms the plugin hasn't broken everything!
The tests for django-plugin-django-header [ https://substack.com/redirect/c75aa8de-9bd9-4327-a3eb-562aaf52f9d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and for django-plugin-blog [ https://substack.com/redirect/f0a917e1-e297-47a2-a29c-3395c0edc5c7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] should provide a useful starting point for writing tests for your own plugins.
Why call it DJP?
Because django-plugins [ https://substack.com/redirect/10cc71c4-c768-4f46-a4c3-cafd342327f1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] already existed on PyPI, and I like my three letter acronyms [ https://substack.com/redirect/a408ebe0-e4e5-413f-bafd-18bd0bd2ad4a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] there!
What's next for DJP?
I presented this at DjangoCon US 2024 yesterday afternoon. Initial response seemed positive, and I'm going to be attending the conference sprints on Thursday morning to see if anyone wants to write their own plugin or help extend the system further.
Is this a good idea? I think so. Plugins have been transformative for both Datasette and LLM, and I think Pluggy [ https://substack.com/redirect/7157bd7b-02db-4741-8018-55289d591d47?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] provides a mature, well-designed foundation for this kind of system.
I'm optimistic about plugins as a natural extension of Django's existing ecosystem. Let's see where this goes.
Notes on using LLMs for code [ https://substack.com/redirect/0f0c378a-7dd9-41f9-9b9b-794ebfbb2a68?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-20
I was recently the guest on TWIML - the This Week in Machine Learning & AI podcast. Our episode is titled Supercharging Developer Productivity with ChatGPT and Claude with Simon Willison [ https://substack.com/redirect/0f30edd2-24ea-4a89-96bb-29e4ad745a23?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and the focus of the conversation was the ways in which I use LLM tools in my day-to-day work as a software developer and product engineer.
Here's the YouTube video [ https://substack.com/redirect/ef3c7e06-9405-4eb9-95b2-b487a8dc3646?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] version of the episode:
I ran the transcript through MacWhisper and extracted some edited highligts below.
Two different modes of LLM use
At 19:53 [ https://substack.com/redirect/942da738-1777-4280-854e-6e2cc2b2f470?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
There are two different modes that I use LLMs for with programming.
The first is exploratory mode, which is mainly quick prototyping - sometimes in programming languages I don't even know.
I love asking these things to give me options. I will often start a prompting session by saying, "I want to draw a visualization of an audio wave. What are my options for this?"
And have it just spit out five different things. Then I'll say "Do me a quick prototype of option three that illustrates how that would work."
The other side is when I'm writing production code, code that I intend to ship, then it's much more like I'm treating it basically as an intern who's faster at typing than I am.
That's when I'll say things like, "Write me a function that takes this and this and returns exactly that."
I'll often iterate on these a lot. I'll say, "I don't like the variable names you used there. Change those." Or "Refactor that to remove the duplication."
I call it my weird intern, because it really does feel like you've got this intern who is screamingly fast, and they've read all of the documentation for everything, and they're massively overconfident, and they make mistakes and they don't realize them.
But crucially, they never get tired, and they never get upset. So you can basically just keep on pushing them and say, "No, do it again. Do it differently. Change that. Change that."
At three in the morning, I can be like, "Hey, write me 100 lines of code that does X, Y, and Z," and it'll do it. It won't complain about it.
It's weird having this small army of super talented interns that never complain about anything, but that's kind of how this stuff ends up working.
Here are all of my other notes about AI-assisted programming [ https://substack.com/redirect/b0eab08b-88af-4ab5-89fa-2f314dee58e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Prototyping
At 25:22 [ https://substack.com/redirect/099c941a-3573-4040-920b-c763bfa93770?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
My entire career has always been about prototyping.
Django itself, the web framework, we built that in a local newspaper so that we could ship features that supported news stories faster. How can we make it so we can turn around a production-grade web application in a few days?
Ever since then, I've always been interested in finding new technologies that let me build things quicker, and my development process has always been to start with a prototype.
You have an idea, you build a prototype that illustrates the idea, you can then have a better conversation about it. If you go to a meeting with five people, and you've got a working prototype, the conversation will be so much more informed than if you go in with an idea and a whiteboard sketch.
I've always been a prototyper, but I feel like the speed at which I can prototype things in the past 12 months has gone up by an order of magnitude.
I was already a very productive prototype producer. Now, I can tap a thing into my phone, and 30 seconds later, I've got a user interface in Claude Artifacts that illustrates the idea that I'm trying to explore.
Honestly, if I didn't use these models for anything else, if I just used them for prototyping, they would still have an enormous impact on the work that I do.
Here are examples of prototypes [ https://substack.com/redirect/1afe2b13-3093-4847-aeff-3f85e2527731?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I've built using Claude Artifacts. A lot of them end up in my tools collection [ https://substack.com/redirect/018056c6-3743-41db-9107-804939e2cfd6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The full conversation covers a bunch of other topics. I ran the transcript through Claude, told it "Give me a bullet point list of the most interesting topics covered in this transcript" and then deleted the ones that I didn't think were particularly interesting - here's what was left:
Using AI-powered voice interfaces like ChatGPT's Voice Mode to code while walking a dog
Leveraging AI tools like Claude and ChatGPT for rapid prototyping and development
Using AI to analyze and extract data from images, including complex documents like campaign finance reports
The challenges of using AI for tasks that may trigger safety filters, particularly for journalism
The evolution of local AI models like Llama and their improving capabilities
The potential of AI for data extraction from complex sources like scanned tables in PDFs
Strategies for staying up-to-date with rapidly evolving AI technologies
The development of vision-language models and their applications
The balance between hosted AI services and running models locally
The importance of examples in prompting for better AI performance
Things I've learned serving on the board of the Python Software Foundation [ https://substack.com/redirect/21300948-2c2d-4a15-bf61-48cd7b5b0d5a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-18
Two years ago I was elected [ https://substack.com/redirect/9633a9a2-a4c0-4056-a969-9a68da04ec6b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to the board of directors for the Python Software Foundation [ https://substack.com/redirect/54dafe7b-4c00-40ad-8e5e-c2a00410e250?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - the PSF. I recently returned from the annual PSF board retreat (this one was in Lisbon, Portugal) and this feels like a good opportunity to write up some of the things I've learned along the way.
What is the PSF? [ https://substack.com/redirect/d9063b40-8476-456c-a715-322a306b938f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The PSF employs staff [ https://substack.com/redirect/a774459c-7a59-4e37-a63a-0ca68179704f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
A lot of this is about money [ https://substack.com/redirect/0bbea37f-c573-4c29-940d-3c53c73dba05?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The PSF does not directly develop Python itself [ https://substack.com/redirect/2f66dee4-fc7d-4e63-8578-9272a484fc85?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
PyPI - the Python Package Index [ https://substack.com/redirect/46144f8a-620c-433c-9e56-24aa69beaa2d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
PyCon is a key commitment [ https://substack.com/redirect/d44086a0-cdaa-4423-bdd8-bc4568383453?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Other PSF activities [ https://substack.com/redirect/8f1ec448-5afa-4576-9841-dcae72b4eadc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Work Groups [ https://substack.com/redirect/7beecbbc-fb64-471d-a9c7-05cd3f9c5e25?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Acting as a fiscal sponsor [ https://substack.com/redirect/866759a0-34e8-443d-bb25-764a628a6402?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Life as a board member [ https://substack.com/redirect/98868edc-3a68-4fa3-86ef-1e616128230b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The kinds of things the board talks about [ https://substack.com/redirect/fbecdbcf-b32d-4da7-96b3-da401f526638?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Want to know more? [ https://substack.com/redirect/62b77701-8e07-46c1-9652-4f81966f5e3a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
What is the PSF?
The PSF is a US 501(c)(3) [ https://substack.com/redirect/96960ac6-5db8-45ed-a54f-61fbb6c8adfc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] non-profit organization with the following mission [ https://substack.com/redirect/56b5b47b-bfca-4839-95da-905e0a0e8bb5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The mission of the Python Software Foundation is to promote, protect, and advance the Python programming language, and to support and facilitate the growth of a diverse and international community of Python programmers.
That mission definition is really important. Board members and paid staff come and go, but the mission remains constant - it's the single most critical resource to help make decisions about whether the PSF should be investing time, money and effort into an activity or not.
The board's 501(c)(3) status is predicated on following the full expanded mission statement [ https://substack.com/redirect/56b5b47b-bfca-4839-95da-905e0a0e8bb5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. When our finances get audited (we conduct an annual "friendly audit", which is considered best practice for organizations at our size), the auditors need to be able to confirm that we've been supporting that mission through our management of the tax-exempt funds that have been entrusted to us.
This auditability is an interesting aspect of how 501(c)(3) organizations work, because it means you can donate funds to them and know that the IRS will ostensibly be ensuring that the money is spent in a way that supports their stated mission.
Board members have fiduciary responsibility for the PSF. A good explanation of this can be found here on BoardSource [ https://substack.com/redirect/f87e8867-6011-4be4-adbd-a82c3086e708?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which also has other useful resources for understanding the roles and responsibilities [ https://substack.com/redirect/56199d47-7bf9-4acb-85ea-0c3fa46bcb52?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of non-profit board members.
(Developing at least a loose intuition for US tax law around non-profits is one of the many surprising things that are necessary to be an effective board member.)
The PSF employs staff
The PSF currently employs 12 full-time staff members [ https://substack.com/redirect/19c49e34-aca7-45e2-be91-77b960e06c5d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Members of the board do not directly manage the activities of the staff - in fact board members telling staff what to do is highly inappropriate.
Instead, the board is responsible for hiring an Executive Director - currently Deb Nicholson - who is then responsible for hiring and managing (directly on indirectly) those other staff members. The board is responsible for evaluating the Executive Director's performance.
I joined the board shortly after Deb was hired, so I have not personally been part of a board hiring committee for a new Executive Director.
While paid staff support and enact many of the activities of the PSF, the foundation is fundamentally a volunteer-based organization. Many PSF activities are carried out by these volunteers [ https://substack.com/redirect/f125f1ec-8ba4-433d-a17a-56a850b37c4c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], in particular via Work Groups [ https://substack.com/redirect/7beecbbc-fb64-471d-a9c7-05cd3f9c5e25?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
A lot of this is about money
A grossly simplified way to think about the PSF is that it's a bucket of money that is raised from sponsors [ https://substack.com/redirect/ba00bd76-8402-43b3-b0a5-4c63da6f8f55?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the Python community (via donations and membership fees), and then spent to support the community and the language in different ways.
The PSF spends money on staff, on grants to Python-related causes and on infrastructure and activities that support Python development and the Python community itself.
You can see how that money has been spent in the 2023 Annual Impact Report [ https://substack.com/redirect/386561f5-f023-454e-b746-28ea9cbde69c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The PSF had $4,356,000 revenue for that year and spent $4,508,000 - running a small loss, but not a concerning one given our assets from previous years.
The most significant categories of expenditure in 2023 were PyCon US ($1,800,000), our Grants program ($677,000), Infrastructure (including PyPI) ($286,000) and our Fiscal Sponsorees ($204,000) - I'll describe these in more detail below.
The PSF does not directly develop Python itself
This is an important detail to understand. The PSF is responsible for protecting and supporting the Python language and community, but development of CPython [ https://substack.com/redirect/62719db9-c421-45a8-9ace-3dfa49aca3b4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] itself is not directly managed by the PSF.
Python development is handled by the Python core team [ https://substack.com/redirect/8069edd6-55f7-499e-8703-4348a3b904bf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], who are governed by the 5-person Python Steering Council [ https://substack.com/redirect/96517b4b-5f95-47bd-bfbf-a597d8155294?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The Steering Council is elected by the core team. The process for becoming a core developer is described here [ https://substack.com/redirect/5052f91a-53fb-420b-9c98-1df6f3b9b2ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
How this all works is defined by PEP 13: Python Language Governance [ https://substack.com/redirect/fc715485-5219-4101-ba9d-bc815e1edf30?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (and several subsequent PEPs). This structure was created - with much discussion - after Guido van Rossum stepped down from his role as Python BDFL in 2018.
The PSF's executive director maintains close ties with the steering council, meeting with them 2-3 times a month. The PSF provides financial support for some Python core activities, such as infrastructure used for Python development and sponsoring travel to and logistics for core Python sprints.
More recently, the PSF has started employing Developers in Residence to directly support the work of both the core Python team and initiatives such as the Python Package Index.
PyPI - the Python Package Index
One of the most consequential projects directly managed by the PSF is PyPI [ https://substack.com/redirect/da924775-96d7-4791-aa51-dccdb88032a7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], the Python Package Index. This is the system that enables pip install name-of-package to do its thing.
Having PyPI managed by a non-profit that answers directly to the community it serves is a very good thing.
PyPI's numbers are staggering. Today there are 570,000 projects consisting of 12,035,133 files, serving 1.9 billion downloads a day (that number from PyPI Stats [ https://substack.com/redirect/3b300060-7e72-4b40-8c64-11dadd8ad8e3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]). Bandwidth for these downloads is donated by Fastly [ https://substack.com/redirect/89935aaf-d1c6-41e4-a0cf-b875fe0e9c8c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a PSF Visionary Sponsor who recently signed a five year agreement [ https://substack.com/redirect/8751ad26-b0e7-4ded-85b7-24b311e115bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to continue this service.
(This was a big deal - prior to that agreement there was concern over what would happen if Fastly ever decided to end that sponsorship.)
PyCon is a key commitment
The annual US Python Conference - PyCon US [ https://substack.com/redirect/c97d3a83-f2b9-4c0a-b3ac-a2095892116e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - is a big part of the PSF's annual activities and operations. With over 3,000 attendees each year (and a $1.8m budget for 2023) running that conference represents a full-time job for several PSF staff members.
In the past PyCon US has also been responsible for the majority of the PSF's operating income. This is no longer true today - in fact it ran at a slight loss this year. This is not a big problem: the PSF's funding has diversified, and the importance of PyCon US to the Python community is such that the PSF is happy to lose money running the event if necessary.
Other PSF activities
Many of these are detailed in the full mission statement [ https://substack.com/redirect/56b5b47b-bfca-4839-95da-905e0a0e8bb5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Operating python.org [ https://substack.com/redirect/906fc5fe-ad66-45dd-9db1-27c44b10781e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and making Python available to download. It's interesting to note that Python is distributed through many alternative routes that are not managed by the PSF - through Linux packaging systems like Ubuntu, Debian and Red Hat, via tools like Docker or Homebrew, by companies such as Anaconda [ https://substack.com/redirect/06543c79-9fcf-4baf-9b6b-add138106149?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] or through newer channels such as uv [ https://substack.com/redirect/ff1a5153-4e85-4a51-a815-3eb7abdb1d87?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Owning and protecting the Python trademarks and the Python intellectual property rights under the (OSI compliant [ https://substack.com/redirect/be764d2a-337f-48bb-af1f-11538cb4a0f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) Python license. This is one of the fundamental reasons for the organization to exist, but thankfully is one of the smaller commitments in terms of cost and staff time.
Running the annual PyCon US conference.
Operating the Python Packaging Index. Fastly provide the CDN, but the PSF still takes on the task of developing and operating the core PyPI web application and the large amounts of moderation and user support that entails.
Supporting infrastructure used for core Python development, and logistics for core Python sprints.
Issuing grants to Python community efforts.
Caring for fiscal sponsorees.
Supporting the work of PSF Work Groups.
Work Groups
A number of PSF initiatives take place in the form of Work Groups, listed here [ https://substack.com/redirect/60de132c-041b-4146-a2fe-11df12a9c7fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Work Groups are teams of volunteers from the community who collaborate on projects relevant to the PSF's mission.
Each Work Group sets its own cadence and ways of working. Some groups have decisions delegated to them by the board - for example the Grants Work Group for reviewing grant proposals and the Code of Conduct Work Group for enforcing Code of Conduct activity. Others coordinate technical projects such as the Infrastructure Working Group [ https://substack.com/redirect/c7ab2eb7-1667-4e0c-bde6-05f3ef75786b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], who manage and make decisions on various pieces of technical infrastructure relevant to Python and the PSF.
Work Groups are formed by a board vote, with a designated charter. Most recently the board approved a charter [ https://substack.com/redirect/94a45d44-d72f-4b34-a0d3-9e03ce65d9a4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for a new User Success Work Group, focusing on things like improving the new Python user onboarding experience.
Acting as a fiscal sponsor
This is another term I was unfamiliar with before joining the board: the idea of a fiscal sponsor, which is a key role played by the PSF.
Running a non-profit organization is decidedly not-trivial: you need a legal structure, a bank account, accounting, governance, the ability to handle audits - there's a whole lot of complexity behind the scenes.
Looking to run an annual community conference? You'll need a bank account, and an entity that can sign agreements with venues and vendors.
Want to accept donations to support work you are doing? Again, you need an entity, and a bank account, and some form of legal structure that ensures your donors can confidently trust you with their money.
Instead of forming a whole new non-profit for this, you can instead find an existing non-profit that is willing to be your "fiscal sponsor". They'll handle the accounting and various other legal aspects, which allows you to invest your efforts in the distinctive work that you are trying to do.
The PSF acts as a fiscal sponsor for a number of different organizations - 20 as-of the 2023 report - including PyLadies, Twisted, Pallets, Jazzband, PyCascades and North Bay Python. The PSF's accounting team invest a great deal of effort in making all of this work.
The PSF generally takes a 10% cut of donations to its fiscal sponsorees. This doesn't actually cover the full staffing cost of servicing these organizations, but this all still makes financial sense in terms of the PSF's mission to support the global Python community.
Life as a board member
There are 12 board members. Elections are held every year after PyCon US, voted on by the PSF membership - by both paid members and members who have earned voting rights through being acknowledged as PSF fellows.
Board members are elected for three year terms. Since 1-3 new board members are likely to join annually, these terms ensure there is overlap which helps maintain institutional knowledge about how the board operates.
The board's activities are governed by the PSF Bylaws [ https://substack.com/redirect/af63bcf8-30dc-4f8c-8074-632a48a05267?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and there is a documented process for modifying them (see ARTICLE XI).
We have board members from all over the world. This is extremely important, because the PSF is responsible for the health and growth of the global Python community. A perennial concern is how to ensure that board candidates are nominated from around the world, in order to maintain that critical global focus.
The board meets once a month over Zoom, has ongoing conversations via Slack and meets in-person twice a year: once at PyCon US and once at a "retreat" in a different global city, selected to try and minimize the total amount of travel needed to get all of our global board members together in the same place.
Our most recent retreat was in Lisbon, Portugal. The retreat before that was in Malmö in Sweden.
I considered using an analogy that describes each board member as 1/12th of the "brain" of the PSF, but that doesn't hold up: the paid, full-time staff of the PSF make an enormous number of decisions that impact how the PSF works.
Instead, the board acts to set strategy, represent the global community and help ensure that the PSF's activities are staying true to that mission. Like I said earlier, the mission definition really is critical. I admit that in the past I've been a bit cynical about the importance of mission statements: being a board member of a 501(c)(3) non-profit has entirely cured me of that skepticism!
Board members can also sit on board committees, of which there are currently four: the Executive Committee, Finance Committee, PyCon US Committee and Membership Committee. These mainly exist so that relevant decisions can be delegated to them, helping reduce the topics that must be considered by the full board in our monthly meetings.
The kinds of things the board talks about
Our Lisbon retreat involved two full 9-hour days of discussion, plus social breakfasts, lunches and dinners. It was an intense workload.
I won't even attempt to do it justice here, but I'll use a couple of topics to illustrate the kind of things we think about on the board.
The first is our grants strategy. The PSF financially sponsors Python community events around the world. In the past this grants program has suffered from low visibility and, to simplify, we've felt that we weren't giving away enough money.
Over the past year we've fixed that: board outreach around the grants program and initiatives such as grants office hours have put our grants program in a much healthier position... but potentially too healthy.
We took steps to improve that visibily and streamline that process, and they worked! This gives us a new problem: we now have no shortage of applicants, so we need to figure out how to stick within a budget that won't harm the financial sustainability of the PSF itself.
Does this mean we say no to more events? Should we instead reduce the size of our grants? Can we take other initiatives, like more actively helping events find alternative forms of sponsorship?
Grants shouldn't just be about events - but if we're making grants to other initiatives that support the Python community how can we fairly select those, manage the budget allocated to supporting them and maximize the value the Python community gets from the money managed by the PSF?
A much larger topic for the retreat was strategic planning. What should our goals be for the PSF that can't be achieved over a short period of time? Projects and initiatives that might require a one-year, three-year or five-year margin of planning.
Director terms only last three years (though board members can and frequently do stand for re-election), so having these long-term goals planned and documented in detail is crucial.
A five-year plan is not something that can be put together over two days of work, but the in-person meeting is a fantastic opportunity to kick things off and ensure each board member gets to participate in shaping that process.
Want to know more?
The above is by no means a comprehensive manual to the PSF, but it's a good representation of the things I would have found most valuable to understand when I first got involved with the organization.
For a broader set of perspectives on how the board works and what it does, I recommend the FAQs about the PSF Board [ https://substack.com/redirect/1564aad0-d9fd-4b3c-8942-2b7e0e9772ac?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] video on YouTube.
If you're interested in helping the PSF achieve its mission, we would love to have you involved:
Encourage your company to sponsor the PSF directly, or to sponsor Python events worldwide
Volunteer at PyCon US or help with other suitable PSF initiatives
Join a Work Group that's addressing problems you want to help solve
Run your own event and apply for a grant [ https://substack.com/redirect/b83a632d-5748-4d76-a5a8-c614551948ee?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Join the PSF as a voting member and vote in our elections
Run for the board elections yourself!
We're always interested in hearing from our community. We host public office hours on the PSF Discord every month, at different times of day to to cater for people in different timezones - here's the full calendar of upcoming office hours [ https://substack.com/redirect/7a2225cf-5cae-4ea7-93d6-8894e4ccfa13?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Quote 2024-09-13
Believe it or not, the name Strawberry does not come from the “How many r’s are in strawberry” meme. We just chose a random word. As far as we know it was a complete coincidence.
Noam Brown, OpenAI [ https://substack.com/redirect/5d1daaab-ce8a-4fae-a51b-c998eeca5be6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-09-14 Notes on running Go in the browser with WebAssembly [ https://substack.com/redirect/5addaeaf-60cc-4f27-9319-6f1a84103519?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Neat, concise tutorial by Eli Bendersky on compiling Go applications that can then be loaded into a browser using WebAssembly and integrated with JavaScript. Go functions can be exported to JavaScript like this:
js.Global.Set("calcHarmonic", jsCalcHarmonic)
And Go code can even access the DOM using a pattern like this:
doc := js.Global.Get("document")
inputElement := doc.Call("getElementById", "timeInput")
input := inputElement.Get("value")
Bundling the WASM Go runtime involves a 2.5MB file load, but there’s also a TinyGo alternative which reduces that size to a fourth.
Quote 2024-09-14
It's a bit sad and confusing that LLMs ("Large Language Models") have little to do with language; It's just historical. They are highly general purpose technology for statistical modeling of token streams. A better name would be Autoregressive Transformers or something.
They don't care if the tokens happen to represent little text chunks. It could just as well be little image patches, audio chunks, action choices, molecules, or whatever. If you can reduce your problem to that of modeling token streams (for any arbitrary vocabulary of some set of discrete tokens), you can "throw an LLM at it".
Andrej Karpathy [ https://substack.com/redirect/8466de66-e2b3-4786-ba4c-363fc94c44ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-09-15
[… OpenAI’s o1] could work its way to a correct (and well-written) solution ifprovided a lot of hints and prodding, but did not generate the key conceptual ideas on its own, and did make some non-trivial mistakes. The experience seemed roughly on par with trying to advise a mediocre, but not completely incompetent, graduate student. However, this was an improvement over previous models, whose capability was closer to an actually incompetent graduate student.
Terrence Tao [ https://substack.com/redirect/f49b3088-92e2-403a-8bc5-cb222f256241?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-09-15 Speed matters [ https://substack.com/redirect/6d367c6d-c1c1-40ee-9ad4-bd30a3181c85?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Jamie Brandon in 2021, talking about the importance of optimizing for the speed at which you can work as a developer:
Being 10x faster also changes the kinds of projects that are worth doing.
Last year I spent something like 100 hours writing a text editor. […] If I was 10x slower it would have been 20-50 weeks. Suddenly that doesn't seem like such a good deal any more - what a waste of a year!
It’s not just about speed of writing code:
When I think about speed I think about the whole process - researching, planning, designing, arguing, coding, testing, debugging, documenting etc.
Often when I try to convince someone to get faster at one of those steps, they'll argue that the others are more important so it's not worthwhile trying to be faster. Eg choosing the right idea is more important than coding the wrong idea really quickly.
But that's totally conditional on the speed of everything else! If you could code 10x as fast then you could try out 10 different ideas in the time it would previously have taken to try out 1 idea. Or you could just try out 1 idea, but have 90% of your previous coding time available as extra idea time.
Jamie’s model here helps explain the effect I described in AI-enhanced development makes me more ambitious with my projects [ https://substack.com/redirect/a7ab29da-41bf-425d-90f7-aca41e9ae955?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Prompting an LLM to write portions of my code for me gives me that 5-10x boost in the time I spend typing code into a computer, which has a big effect on my ambitions despite being only about 10% of the activities I perform relevant to building software.
I also increasingly lean on LLMs as assistants in the research phase - exploring library options, building experimental prototypes - and for activities like writing tests and even a little bit of documentation [ https://substack.com/redirect/00baff43-2a81-4c93-826a-6770a8184086?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-09-15 How to succeed in MrBeast production (leaked PDF) [ https://substack.com/redirect/f4583875-a585-4eab-939a-7b6993479b8d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Whether or not you enjoy MrBeast’s format of YouTube videos (here’s a 2022 Rolling Stone profile [ https://substack.com/redirect/6d11bebf-2900-4f6c-b446-9d127a82acbf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] if you’re unfamiliar), this leaked onboarding document for new members of his production company is a compelling read.
It’s a snapshot of what it takes to run a massive scale viral YouTube operation in the 2020s, as well as a detailed description of a very specific company culture evolved to fulfill that mission.
It starts in the most on-brand MrBeast way possible:
I genuinely believe if you attently read and understand the knowledge here you will be much better set up for success. So, if you read this book and pass a quiz I’ll give you $1,000.
Everything is focused very specifically on YouTube as a format:
Your goal here is to make the best YOUTUBE videos possible. That’s the number one goal of this production company. It’s not to make the best produced videos. Not to make the funniest videos. Not to make the best looking videos. Not the highest quality videos.. It’s to make the best YOUTUBE videos possible.
The MrBeast definition of A, B and C-team players is one I haven’t heard before:
A-Players are obsessive, learn from mistakes, coachable, intelligent, don’t make excuses, believe in Youtube, see the value of this company, and are the best in the goddamn world at their job. B-Players are new people that need to be trained into A-Players, and C-Players are just average employees. […] They arn’t obsessive and learning. C-Players are poisonous and should be transitioned to a different company IMMEDIATELY. (It’s okay we give everyone severance, they’ll be fine).
The key characteristic outlined here, if you read between the hustle-culture lines, is learning. Employees who constantly learn are valued. Employees who don’t are not.
There’s a lot of stuff in there about YouTube virality, starting with the Click Thru Rate (CTR) for the all-important video thumbnails:
This is what dictates what we do for videos. “I Spent 50 Hours In My Front Yard” is lame and you wouldn’t click it. But you would hypothetically click “I Spent 50 Hours In Ketchup”. Both are relatively similar in time/effort but the ketchup one is easily 100x more viral. An image of someone sitting in ketchup in a bathtub is exponentially more interesting than someone sitting in their front yard.
The creative process for every video they produce starts with the title and thumbnail. These set the expectations for the viewer, and everything that follows needs to be defined with those in mind. If a viewer feels their expectations are not being matched, they’ll click away - driving down the crucial Average View Duration that informs how much the video is promoted by YouTube’s all-important mystical algorithms.
MrBeast videos have a strictly defined formula, outlined in detail on pages 6-10.
The first minute captures the viewer’s attention and demonstrates that their expectations from the thumbnail will be met. Losing 21 million viewers in the first minute after 60 million initial clicks is considered a reasonably good result! Minutes 1-3, 3-6 and 6-end all have their own clearly defined responsibilities as well.
Ideally, a video will feature something they call the “wow factor”:
An example of the “wow factor” would be our 100 days in the circle video. We offered someone $500,000 if they could live in a circle in a field for 100 days (video [ https://substack.com/redirect/2820f4f1-e641-4f74-a7bf-ff5f3021dd09?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and instead of starting with his house in the circle that he would live in, we bring it in on a crane 30 seconds into the video. Why? Because who the fuck else on Youtube can do that lol.
Chapter 2 (pages 10-24) is about creating content. This is crammed with insights into what it takes to produce surprising, spectacular and very expensive content for YouTube.
A lot of this is about coordination and intense management of your dependencies:
I want you to look them in the eyes and tell them they are the bottleneck and take it a step further and explain why they are the bottleneck so you both are on the same page. “Tyler, you are my bottleneck. I have 45 days to make this video happen and I can not begin to work on it until I know what the contents of the video is. I need you to confirm you understand this is important and we need to set a date on when the creative will be done.” […] Every single day you must check in on Tyler and make sure he is still on track to hit the target date.
It also introduces the concept of “critical components”:
Critical components are the things that are essential to your video. If I want to put 100 people on an island and give it away to one of them, then securing an island is a critical component. It doesn’t matter how well planned the challenges on the island are, how good the weather is, etc. Without that island there is no video.
[…]
Critical Components can come from literally anywhere and once something you’re working on is labeled as such, you treat it like your baby. WITHOUT WHAT YOU’RE WORKING ON WE DO NOT HAVE A VIDEO! Protect it at all costs, check in on it 10x a day, obsess over it, make a backup, if it requires shipping pay someone to pick it up and drive it, don’t trust standard shipping, and speak up the second anything goes wrong. The literal second. Never coin flip a Critical Component (that means you’re coinfliping the video aka a million plus dollars)
There’s a bunch of stuff about communication, with a strong bias towards “higher forms of communication”: in-person beats a phone call beats a text message beats an email.
Unsurprisingly for this organization, video is a highly valued tool for documenting work:
Which is more important, that one person has a good mental grip of something or that their entire team of 10 people have a good mental grip on something? Obviously the team. And the easiest way to bring your team up to the same page is to freaken video everything and store it where they can constantly reference it. A lot of problems can be solved if we just video sets and ask for videos when ordering things.
I enjoyed this note:
Since we are on the topic of communication, written communication also does not constitute communication unless they confirm they read it.
And this bit about the value of consultants:
Consultants are literally cheat codes. Need to make the world's largest slice of cake? Start off by calling the person who made the previous world’s largest slice of cake lol. He’s already done countless tests and can save you weeks worth of work. […] In every single freakin task assigned to you, always always always ask yourself first if you can find a consultant to help you.
Here’s a darker note from the section “Random things you should know”:
Do not leave consteatants waiting in the sun (ideally waiting in general) for more than 3 hours. Squid game it cost us $500,000 and boys vs girls it got a lot of people out. Ask James to know more
And to finish, this note on budgeting:
I want money spent to be shown on camera ideally. If you’re spending over $10,000 on something and it won’t be shown on camera, seriously think about it.
I’m always interested in finding management advice from unexpected sources. For example, I love The Eleven Laws of Showrunning [ https://substack.com/redirect/6fee7163-4664-47c6-8ff8-b8f15624285c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as a case study in managing and successfully delegating for a large, creative project.
I don’t think this MrBeast document has as many lessons directly relevant to my own work, but as an honest peek under the hood of a weirdly shaped and absurdly ambitious enterprise it’s legitimately fascinating.
Link 2024-09-15 UV — I am (somewhat) sold [ https://substack.com/redirect/715e5a3c-3303-413d-9dfe-3beac9c490fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Oliver Andrich's detailed notes on adopting uv. Oliver has some pretty specific requirements:
I need to have various Python versions installed locally to test my work and my personal projects. Ranging from Python 3.8 to 3.13. [...] I also require decent dependency management in my projects that goes beyond manually editing a pyproject.toml file. Likewise, I am way too accustomed to poetry add .... And I run a number of Python-based tools --- djhtml [ https://substack.com/redirect/878d2efe-31d7-4903-9f11-c5e9973fc90d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], poetry [ https://substack.com/redirect/05e65fa8-bd59-4e03-b660-97ba1733b1b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], ipython [ https://substack.com/redirect/9006f4cf-e707-4693-b501-08bfd3c1fd2d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], llm [ https://substack.com/redirect/a408ebe0-e4e5-413f-bafd-18bd0bd2ad4a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], mkdocs [ https://substack.com/redirect/4baebaf2-36da-4242-993b-8c095a22f218?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], pre-commit [ https://substack.com/redirect/3b3833a2-1fb9-465a-b833-0926652c7e64?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], tox [ https://substack.com/redirect/d493fe7e-6f1b-461b-8931-0ece03c69643?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], ...
He's braver than I am!
I started by removing all Python installations, pyenv, pipx and Homebrew from my machine. Rendering me unable to do my work.
Here's a neat trick: first install a specific Python version with uv like this:
uv python install 3.11
Then create an alias to run it like this:
alias python3.11 'uv run --python=3.11 python3'
And install standalone tools with optional extra dependencies like this (a replacement for pipxand pipx inject):
uv tool install --python=3.12 --with mkdocs-material mkdocs
Oliver also links to Anže Pečar's handy guide on using UV with Django [ https://substack.com/redirect/2382c1ba-d870-45aa-ab5e-93fa7922d4da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Quote 2024-09-16
o1 prompting is alien to me. Its thinking, gloriously effective at times, is also dreamlike and unamenable to advice.
Just say what you want and pray. Any notes on “how” will be followed with the diligence of a brilliant intern on ketamine.
Riley Goodside [ https://substack.com/redirect/1665505d-85e6-4519-bfd6-33f0127f2a9c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-09-17
Do not fall into the trap of anthropomorphizing Larry Ellison. You need to think of Larry Ellison the way you think of a lawnmower. You don’t anthropomorphize your lawnmower, the lawnmower just mows the lawn - you stick your hand in there and it’ll chop it off, the end. You don’t think "oh, the lawnmower hates me" – lawnmower doesn’t give a shit about you, lawnmower can’t hate you. Don’t anthropomorphize the lawnmower. Don’t fall into that trap about Oracle.
Bryan Cantrill [ https://substack.com/redirect/d4eb0f20-bd0d-424d-8361-1d790b59d3d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-09-17 Supercharging Developer Productivity with ChatGPT and Claude with Simon Willison [ https://substack.com/redirect/0f30edd2-24ea-4a89-96bb-29e4ad745a23?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I'm the guest for the latest episode of the TWIML AI podcast [ https://substack.com/redirect/d57e97fc-3a6f-4f2f-a850-a89cfb524fdf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - This Week in Machine Learning & AI, hosted by Sam Charrington.
We mainly talked about how I use LLM tooling for my own work - Claude, ChatGPT, Code Interpreter, Claude Artifacts, LLM and GitHub Copilot - plus a bit about my experiments with local models.
Link 2024-09-17 Serializing package requirements in marimo notebooks [ https://substack.com/redirect/6ac0218c-283f-404b-9daf-322f3e74fa09?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The latest release [ https://substack.com/redirect/ef36d3b0-66f0-4577-8e33-3864405db28b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of Marimo [ https://substack.com/redirect/0284eb76-c4d2-4528-91a4-f5055789bc96?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - a reactive alternative to Jupyter notebooks - has a very neat new feature enabled by its integration with uv [ https://substack.com/redirect/a5c12c22-e612-4af9-9bf1-1bee9c3ba6ad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
One of marimo’s goals is to make notebooks reproducible, down to the packages used in them. To that end, it’s now possible to create marimo notebooks that have their package requirements serialized into them as a top-level comment.
This takes advantage of the PEP 723 [ https://substack.com/redirect/2736ae88-31bc-4872-81a5-1321300316e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] inline metadata mechanism, where a code comment at the top of a Python file can list package dependencies (and their versions).
I tried this out by installing marimo using uv:
uv tool install --python=3.12 marimo
Then grabbing one of their example notebooks [ https://substack.com/redirect/55156693-690c-4dd5-b600-4f7a86fdb32d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
wget 'https://raw.githubusercontent.com/marimo-team/spotlights/main/001-anywidget/tldraw_colorpicker.py'
And running it in a fresh dependency sandbox like this:
marimo run --sandbox tldraw_colorpicker.py
Also neat is that when editing a notebook using marimo edit:
marimo edit --sandbox notebook.py
Just importing a missing package is enough for Marimo to prompt to add that to the dependencies - at which point it automatically adds that package to the comment at the top of the file:
Quote 2024-09-17
Something that I confirmed that other conference organisers are also experiencing is last-minute ticket sales. This is something that happened with UX London this year. For most of the year, ticket sales were trickling along. Then in the last few weeks before the event we sold more tickets than we had sold in the six months previously. […]
When I was in Ireland I had a chat with a friend of mine who works at the Everyman Theatre in Cork. They’re experiencing something similar. So maybe it’s not related to the tech industry specifically.
Jeremy Keith [ https://substack.com/redirect/9a2e2f31-65e2-4f06-9cb3-4595509c36b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-09-17
In general, the claims about how long people are living mostly don’t stack up. I’ve tracked down 80% of the people aged over 110 in the world (the other 20% are from countries you can’t meaningfully analyse). Of those, almost none have a birth certificate. [...]
Regions where people most often reach 100-110 years old are the ones where there’s the most pressure to commit pension fraud, and they also have the worst records.
Saul Justin Newman [ https://substack.com/redirect/6dbea906-7005-4c8c-88ea-d8cf63271bc8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-09-17 Oracle, it’s time to free JavaScript. [ https://substack.com/redirect/d50cda88-b319-4245-a28e-7bd7daf5fda9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Oracle have held the trademark on JavaScript since their acquisition of Sun Microsystems in 2009. They’ve continued to renew that trademark over the years despite having no major products that use the mark.
Their December 2019 renewal included a screenshot of the Node.js homepage [ https://substack.com/redirect/6d917e51-83a8-4a7b-8232-d2cc4299ce90?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as a supporting specimen!
Now a group lead by a team that includes Ryan Dahl and Brendan Eich is coordinating a legal challenge to have the USPTO treat the trademark as abandoned and “recognize it as a generic name for the world’s most popular programming language, which has multiple implementations across the industry.”
Quote 2024-09-18
The problem that you face is that it's relatively easy to take a model and make it look like it's aligned. You ask GPT-4, “how do I end all of humans?” And the model says, “I can't possibly help you with that”. But there are a million and one ways to take the exact same question - pick your favorite - and you can make the model still answer the question even though initially it would have refused. And the question this reminds me a lot of coming from adversarial machine learning. We have a very simple objective: Classify the image correctly according to the original label. And yet, despite the fact that it was essentially trivial to find all of the bugs in principle, the community had a very hard time coming up with actually effective defenses. We wrote like over 9,000 papers in ten years, and have made very very very limited progress on this one small problem. You all have a harder problem and maybe less time.
Nicholas Carlini [ https://substack.com/redirect/7e5b193c-6ed1-446d-b943-02ce08a3580d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-09-19 The web's clipboard, and how it stores data of different types [ https://substack.com/redirect/59661a09-2893-45b0-8384-429b4ed51be5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Alex Harri's deep dive into the Web clipboard API [ https://substack.com/redirect/14982e96-1265-488c-abd7-12362292a3fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], the more recent alternative to the old document.execCommand mechanism for accessing the clipboard.
There's a lot to understand here! Some of these APIs have a history dating back to Internet Explorer 4 in 1997, and there have been plenty of changes over the years to account for improved understanding of the security risks of allowing untrusted code to interact with the system clipboard.
Today, the most reliable data formats for interacting with the clipboard are the "standard" formats of text/plain, text/html and image/png.
Figma does a particularly clever trick where they share custom Figma binary data structures by encoding them as base64 in data-metadataand data-buffer attributes on a  element, then write the result to the clipboard as HTML. This enables copy-and-paste between the Figma web and native apps via the system clipboard.
Link 2024-09-19 Moshi [ https://substack.com/redirect/6ba2e107-c2ec-46ad-93c8-4e487e4dbb09?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Moshi is "a speech-text foundation model and full-duplex spoken dialogue framework". It's effectively a text-to-text model - like an LLM but you input audio directly to it and it replies with its own audio.
It's fun to play around with, but it's not particularly useful in comparison to other pure text models: I tried to talk to it about California Brown Pelicans and it gave me some very basic hallucinated thoughts about California Condors instead.
It's very easy to run locally, at least on a Mac (and likely on other systems too). I used uv and got the 8 bit quantized version running as a local web server using this one-liner:
uv run --with moshi_mlx python -m moshi_mlx.local_web -q 8
That downloads ~8.17G of model to a folder in ~/.cache/huggingface/hub/ - or you can use -q 4 and get a 4.81G version instead (albeit even lower quality).
Link 2024-09-20 Introducing Contextual Retrieval [ https://substack.com/redirect/1e8ec3d9-bb10-47c7-90db-d8b61b1d3098?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Here's an interesting new embedding/RAG technique, described by Anthropic but it should work for any embedding model against any other LLM.
One of the big challenges in implementing semantic search against vector embeddings - often used as part of a RAG system - is creating "chunks" of documents that are most likely to semantically match queries from users.
Anthropic provide this solid example where semantic chunks might let you down:
Imagine you had a collection of financial information (say, U.S. SEC filings) embedded in your knowledge base, and you received the following question: "What was the revenue growth for ACME Corp in Q2 2023?"
A relevant chunk might contain the text: "The company's revenue grew by 3% over the previous quarter." However, this chunk on its own doesn't specify which company it's referring to or the relevant time period, making it difficult to retrieve the right information or use the information effectively.
Their proposed solution is to take each chunk at indexing time and expand it using an LLM - so the above sentence would become this instead:
This chunk is from an SEC filing on ACME corp's performance in Q2 2023; the previous quarter's revenue was $314 million. The company's revenue grew by 3% over the previous quarter."
This chunk was created by Claude 3 Haiku (their least expensive model) using the following prompt template:

{{WHOLE_DOCUMENT}}

Here is the chunk we want to situate within the whole document

{{CHUNK_CONTENT}}

Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else.
Here's the really clever bit: running the above prompt for every chunk in a document could get really expensive thanks to the inclusion of the entire document in each prompt. Claude added context caching [ https://substack.com/redirect/fa83d3f2-e4ce-4ce7-baab-6b9bd8cc992a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] last month, which allows you to pay around 1/10th of the cost for tokens cached up to your specified beakpoint.
By Anthropic's calculations:
Assuming 800 token chunks, 8k token documents, 50 token context instructions, and 100 tokens of context per chunk, the one-time cost to generate contextualized chunks is $1.02 per million document tokens.
Anthropic provide a detailed notebook [ https://substack.com/redirect/553f7240-9587-444c-a970-eabc60164304?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]demonstrating an implementation of this pattern. Their eventual solution combines cosine similarity and BM25 indexing, uses embeddings from Voyage AI [ https://substack.com/redirect/b8a7ae73-d81a-4193-b173-61b463862bf9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and adds a reranking step powered by Cohere [ https://substack.com/redirect/1024d188-58df-4284-9d58-d143dc3471bd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The notebook also includes an evaluation set using JSONL - here's that evaluation data in Datasette Lite [ https://substack.com/redirect/3c195891-9ee9-4cef-b4e0-e3d2485e3170?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-09-20 YouTube Thumbnail Viewer [ https://substack.com/redirect/044fe8c7-5737-4ac8-8754-2126b9067407?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I wanted to find the best quality thumbnail image for a YouTube video, so I could use it as a social media card. I know from past experience that GPT-4 has memorized the various URL patterns for img.youtube.com, so I asked it [ https://substack.com/redirect/7f184b41-cca0-4dec-a47e-c805972e2c5b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to guess the URL for my specific video.
This piqued my interest as to what the other patterns were, so I got it to spit those out too. Then, to save myself from needing to look those up again in the future, I asked it to build me a little HTML and JavaScript tool for turning a YouTube video URL into a set of visible thumbnails.
I iterated on the code [ https://substack.com/redirect/6a9750e4-b2ff-4e91-ab93-953b73b798d2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a bit more after pasting it into Claude and ended up with this, now hosted in my tools [ https://substack.com/redirect/018056c6-3743-41db-9107-804939e2cfd6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] collection.
Link 2024-09-21 Markdown and Math Live Renderer [ https://substack.com/redirect/85554e98-2711-482b-b4f4-3a28c6af8714?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Another of my tiny Claude-assisted JavaScript tools. This one lets you enter Markdown with embedded mathematical expressions (like $ax^2 + bx + c = 0$) and live renders those on the page, with an HTML version using MathML that you can export through copy and paste.
Here's the Claude transcript [ https://substack.com/redirect/683e29ee-ed4d-44c7-846d-30e7eb6a0994?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I started by asking:
Are there any client side JavaScript markdown libraries that can also handle inline math and render it?
Claude gave me several options including the combination of Marked [ https://substack.com/redirect/cec74235-e646-4eb7-8db4-5c590947635c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and KaTeX [ https://substack.com/redirect/6e1d543f-75a5-4b87-a3ba-5ee465afd8fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], so I followed up by asking:
Build an artifact that demonstrates Marked plus KaTeX - it should include a text area I can enter markdown in (repopulated with a good example) and live update the rendered version below. No react.
Which gave me this artifact [ https://substack.com/redirect/36e22b24-4460-464a-a1a2-419929479f18?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], instantly demonstrating that what I wanted to do was possible.
I iterated on it [ https://substack.com/redirect/362f2534-47ab-4443-85f5-74c67c2853a9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a tiny bit to get to the final version, mainly to add that HTML export and a Copy button. The final source code is here [ https://substack.com/redirect/de71d27d-decd-4fb5-9641-cf33384b0aae?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Quote 2024-09-21
Whether you think coding with AI works today or not doesn’t really matter.
But if you think functional AI helping to code will make humans dumber or isn’t real programming just consider that’s been the argument against every generation of programming tools going back to Fortran.
Steven Sinofsky [ https://substack.com/redirect/25674d9d-1281-47f9-8f26-86f87973bdb9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
TIL 2024-09-21 How streaming LLM APIs work [ https://substack.com/redirect/bc957eab-47e9-409f-a8eb-c1e2824e8ad6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I decided to have a poke around and see if I could figure out how the HTTP streaming APIs from the various hosted LLM providers actually worked. Here are my notes so far. …
Link 2024-09-22 How streaming LLM APIs work [ https://substack.com/redirect/bc957eab-47e9-409f-a8eb-c1e2824e8ad6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New TIL. I used curl to explore the streaming APIs provided by OpenAI, Anthropic and Google Gemini and wrote up detailed notes on what I learned.
Also includes example code for receiving streaming events in Python with HTTPX [ https://substack.com/redirect/48dab1d1-30c5-447a-9e97-8a14954320d0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and receiving streaming events in client-side JavaScript using fetch [ https://substack.com/redirect/1f88de51-d956-4ddd-b811-b02e640a8d58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-09-22 Jiter [ https://substack.com/redirect/a82d75d4-164a-4ab2-9720-eb390210cca0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
One of the challenges in dealing with LLM streaming APIs is the need to parse partial JSON - until the stream has ended you won't have a complete valid JSON object, but you may want to display components of that JSON as they become available.
I've solved this previously using the ijson [ https://substack.com/redirect/1430adf5-9924-4742-b394-41d2c6a75bff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]streaming JSON library, see my previous TIL [ https://substack.com/redirect/e7a1f392-ef14-458d-b6f3-93f00dbfb1f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Today I found out about Jiter, a new option from the team behind Pydantic. It's written in Rust and extracted from pydantic-core [ https://substack.com/redirect/54c655dc-85c2-49a1-a9de-fb5ac63709fa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], so the Python wrapper for it can be installed using:
pip install jiter
You can feed it an incomplete JSON bytes object and use partial_mode="on" to parse the valid subset:
import jiter
partial_json = b'{"name": "John", "age": 30, "city": "New Yor'
jiter.from_json(partial_json, partial_mode="on")
# {'name': 'John', 'age': 30}
Or use partial_mode="trailing-strings" to include incomplete string fields too:
jiter.from_json(partial_json, partial_mode="trailing-strings")
# {'name': 'John', 'age': 30, 'city': 'New Yor'}
The current README [ https://substack.com/redirect/6c004201-cb65-428e-9680-65bd656820a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] was a little thin, so I submiitted a PR [ https://substack.com/redirect/4d4f22c9-d9c2-45ff-aa54-1a0bcbabd3c6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with some extra examples. I got some help [ https://substack.com/redirect/9b902189-14fa-4608-ad34-1312d7b7319d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from files-to-prompt and Claude 3.5 Sonnet):
cd crates/jiter-python/ && files-to-prompt -c README.md tests | llm -m claude-3.5-sonnet --system 'write a new README with comprehensive documentation'
Quote 2024-09-22
The problem I have with [pipenv shell] is that the act of manipulating the shell environment is crappy and can never be good. What all these "X shell" things do is just an abomination we should not promote IMO.
Tools should be written so that you do not need to reconfigure shells. That we normalized this over the last 10 years was a mistake and we are not forced to continue walking down that path :)
Armin Ronacher [ https://substack.com/redirect/74bd374b-1f78-4408-8199-a9327725a23e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-09-23
SPAs incur complexity that simply doesn't exist with traditional server-based websites: issues such as search engine optimization, browser history management, web analytics and first page load time all need to be addressed. Proper analysis and consideration of the trade-offs is required to determine if that complexity is warranted for business or user experience reasons. Too often teams are skipping that trade-off analysis, blindly accepting the complexity of SPAs by default even when business needs don't justify it. We still see some developers who aren't aware of an alternative approach because they've spent their entire career in a framework like React.
Thoughtworks, October 2022 [ https://substack.com/redirect/1330ce91-cfcd-4c24-ae9c-243248c99af4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-09-23 simonw/docs cookiecutter template [ https://substack.com/redirect/9ad4d7d9-8377-4370-91ce-1f10d01aeac3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Over the last few years I’ve settled on the combination of Sphinx [ https://substack.com/redirect/3b0851ec-533a-49cb-be1f-5cdea53afa21?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], the Furo [ https://substack.com/redirect/8df12122-d9eb-4adb-bf77-5a5f25158d3d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] theme and the myst-parser [ https://substack.com/redirect/e501a4b9-889a-422e-b9bc-929c1357b8be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] extension (enabling Markdown in place of reStructuredText) as my documentation toolkit of choice, maintained in GitHub and hosted using ReadTheDocs [ https://substack.com/redirect/b4550f7a-e3cd-4749-bd1c-ffd35eef84b3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
My LLM [ https://substack.com/redirect/8553e34e-2554-4df3-b030-59b803cda48f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and shot-scraper [ https://substack.com/redirect/e26eecde-9a4f-48c1-9b71-eea9d6e87647?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] projects are two examples of that stack in action.
Today I wanted to spin up a new documentation site so I finally took the time to construct a cookiecutter [ https://substack.com/redirect/bf0addd3-3f3d-4d6a-8eca-5f9674dbf254?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] template for my preferred configuration. You can use it like this:
pipx install cookiecutter
cookiecutter gh:simonw/docs
Or with uv [ https://substack.com/redirect/a5c12c22-e612-4af9-9bf1-1bee9c3ba6ad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
uv tool run cookiecutter gh:simonw/docs
Answer a few questions:
[1/3] project : shot-scraper
[2/3] author : Simon Willison
[3/3] docs_directory (docs):
And it creates a docs/ directory ready for you to start editing docs:
cd docs
pip install -r requirements.txt
make livehtml
Link 2024-09-24 Things I've Learned Serving on the Board of The Perl Foundation [ https://substack.com/redirect/3d69b208-9af9-4a87-9ed8-8ddd5106d59b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
My post about the PSF board [ https://substack.com/redirect/21300948-2c2d-4a15-bf61-48cd7b5b0d5a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] inspired Perl Foundation secretary Makoto Nozaki to publish similar notes about how TPF (also known since 2019 as TPRF, for The Perl and Raku Foundation) operates.
Seeing this level of explanation about other open source foundations is fascinating. I’d love to see more of these.
Along those lines, I found the 2024 Financial Report [ https://substack.com/redirect/222377da-aed9-4e0b-8038-7762dbb7f2a1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from the Zig foundation really interesting too.
Link 2024-09-24 XKCD 1425 (Tasks) turns ten years old today [ https://substack.com/redirect/fa06861f-a8b6-4b2c-ac0f-f8b8301a74c4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
One of the all-time great XKCDs. It's amazing that "check whether the photo is of a bird" has gone from PhD-level to trivially easy to solve (with a vision LLM [ https://substack.com/redirect/0dd2aed0-c5f2-48f6-8617-dc1f73ce86e4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], or CLIP [ https://substack.com/redirect/cc4700a1-8617-496f-ad31-5557ab8094b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], or ResNet+ImageNet [ https://substack.com/redirect/73c316a0-de22-42a8-a69c-c2d4a6467076?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] among others).
The key idea still very much stands though. Understanding the difference between easy and hard challenges in software development continues to require an enormous depth of experience.
I'd argue that LLMs have made this even worse.
Understanding what kind of tasks LLMs can and cannot reliably solve remains incredibly difficult and unintuitive. They're computer systems that are terrible at maths and that can't reliably lookup facts!
On top of that, the rise of AI-assisted programming tools means more people than ever are beginning to create their own custom software.
These brand new AI-assisted proto-programmers are having a crash course in this easy-v.s.-hard problem.
I saw someone recently complaining that they couldn't build a Claude Artifact that could analyze images, even though they knew Claude itself could do that. Understanding why that's not possible involves understanding how the CSP headers [ https://substack.com/redirect/b310c3f2-fe8d-47a7-8ce2-45eb954bd992?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that are used to serve Artifacts prevent the generated code from making its own API calls out to an LLM!
Link 2024-09-24 nanodjango [ https://substack.com/redirect/b3190f1d-b095-4bf8-aa32-882819ad6c66?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Richard Terry demonstrated this in a lightning talk at DjangoCon US today. It's the latest in a long line of attempts to get Django to work with a single file (I had a go at this problem 15 years ago with djng [ https://substack.com/redirect/877e7e18-0be3-4655-9dc8-aee760698dda?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) but this one is really compelling.
I tried nanodjango out just now and it works exactly as advertised. First install it like this:
pip install nanodjango
Create a counter.py file:
from django.db import models
from nanodjango import Django

app = Django

@app.admin # Registers with the Django admin
class CountLog(models.Model):
timestamp = models.DateTimeField(auto_now_add=True)

@app.route("/")
def count(request):
CountLog.objects.create
return f"Number of page loads: {CountLog.objects.count}

"
Then run it like this (it will run migrations and create a superuser as part of that first run):
nanodjango run counter.py
That's it! This gave me a fully configured Django application with models, migrations, the Django Admin configured and a bunch of other goodies such as Django Ninja [ https://substack.com/redirect/83d6a6f9-f39a-4532-997e-c7b73d2005cd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for API endpoints.
Here's the full documentation [ https://substack.com/redirect/6ee4cc1a-9c54-4f23-bbd7-4cacb5454e9a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-09-24 Updated production-ready Gemini models [ https://substack.com/redirect/4c465c6c-6faf-4bb7-847d-c7811d8b1849?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Two new models from Google Gemini today: gemini-1.5-pro-002 and gemini-1.5-flash-002. Their -latest aliases will update to these new models in "the next few days", and new -001suffixes can be used to stick with the older models. The new models benchmark slightly better in various ways and should respond faster.
Flash continues to have a 1,048,576 input token and 8,192 output token limit. Pro is 2,097,152 input tokens.
Google also announced a significant price reduction for Pro, effective on the 1st of October. Inputs less than 128,000 tokens drop from $3.50/million to $1.25/million (above 128,000 tokens it's dropping from $7 to $5) and output costs drop from $10.50/million to $2.50/million ($21 down to $10 for the >128,000 case).
For comparison, GPT-4o is currently $5/m input and $15/m output and Claude 3.5 Sonnet is $3/m input and $15/m output. Gemini 1.5 Pro was already the cheapest of the frontier models and now it's even cheaper.
Correction: I missed gpt-4o-2024-08-06 which is listed later on the OpenAI pricing page [ https://substack.com/redirect/9b5983e6-9a63-4f9d-9cfe-fe801364524f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and priced at $2.50/m input and $10/m output. So the new Gemini 1.5 Pro prices are undercutting that.
Gemini has always offered finely grained safety filters [ https://substack.com/redirect/bed6150c-f442-496d-b4f0-9e57cdb2c4ae?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - it sounds like those are now turned down to minimum by default, which is a welcome change:
For the models released today, the filters will not be applied by default so that developers can determine the configuration best suited for their use case.
Also interesting: they've tweaked the expected length of default responses:
For use cases like summarization, question answering, and extraction, the default output length of the updated models is ~5-20% shorter than previous models.
Link 2024-09-25 The Pragmatic Engineer Podcast: AI tools for software engineers, but without the hype – with Simon Willison [ https://substack.com/redirect/be9bd5fa-8838-433c-b73a-b9a4db2da249?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Gergely Orosz has a brand new podcast, and I was the guest for the first episode. We covered a bunch of ground, but my favorite topic was an exploration of the (very legitimate) reasons that many engineers are resistant to taking advantage of AI-assisted programming tools.
Quote 2024-09-25
We used this model [periodically transmitting configuration to different hosts] to distribute translations, feature flags, configuration, search indexes, etc at Airbnb. But instead of SQLite we used Sparkey [ https://substack.com/redirect/38c0901f-20af-42fe-b8be-8a58e339ec32?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a KV file format developed by Spotify. In early years there was a Cron job on every box that pulled that service’s thingies; then once we switched to Kubernetes we used a daemonset & host tagging (taints?) to pull a variety of thingies to each host and then ensure the services that use the thingies only ran on the hosts that had the thingies.
Jake Teton-Landis [ https://substack.com/redirect/94ff7140-5c80-45c4-bc1e-b543de9e022c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-09-25 Solving a bug with o1-preview, files-to-prompt and LLM [ https://substack.com/redirect/eb2dab18-ff30-484b-bef9-c0787e119d3c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I added a new feature [ https://substack.com/redirect/b04f7cc9-1016-49da-b469-7cb711ff5fba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to DJP this morning: you can now have plugins specify their metadata in terms of how it should be positioned relative to other metadata - inserted directly before or directly after django.middleware.common.CommonMiddlewarefor example.
At one point I got stuck with a weird test failure, and after ten minutes of head scratching I decided to pipe the entire thing into OpenAI's o1-preview to see if it could spot the problem. I used files-to-prompt [ https://substack.com/redirect/38b4ec59-0d7d-4f90-8955-57b75d8f27fa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to gather the code and LLM [ https://substack.com/redirect/8553e34e-2554-4df3-b030-59b803cda48f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]to run the prompt:
files-to-prompt */.py -c | llm -m o1-preview "
The middleware test is failing showing all of these - why is MiddlewareAfter repeated so many times?

['MiddlewareAfter', 'Middleware3', 'MiddlewareAfter', 'Middleware5', 'MiddlewareAfter', 'Middleware3', 'MiddlewareAfter', 'Middleware2', 'MiddlewareAfter', 'Middleware3', 'MiddlewareAfter', 'Middleware5', 'MiddlewareAfter', 'Middleware3', 'MiddlewareAfter', 'Middleware4', 'MiddlewareAfter', 'Middleware3', 'MiddlewareAfter', 'Middleware5', 'MiddlewareAfter', 'Middleware3', 'MiddlewareAfter', 'Middleware2', 'MiddlewareAfter', 'Middleware3', 'MiddlewareAfter', 'Middleware5', 'MiddlewareAfter', 'Middleware3', 'MiddlewareAfter', 'Middleware', 'MiddlewareBefore']"
The model whirled away for a few seconds and spat outan explanation [ https://substack.com/redirect/e0b2a378-9e8e-45d8-acc5-12b440031624?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]of the problem - one of my middleware classes was accidentally callingself.get_response(request)in two different places.
I did enjoy how o1 attempted to reference the relevant Django documentation [ https://substack.com/redirect/0bb5d2fe-6459-4c96-92e3-42a400b3bf65?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and then half-repeated, half-hallucinated a quote from it:
This took 2,538 input tokens and 4,354 output tokens - by my calculations [ https://substack.com/redirect/8ae68d40-4791-4d84-be9d-bffbc2a39ba1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] at $15/million input and $60/million output that prompt cost just under 30 cents.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hORGswTWpJMk1ERXNJbWxoZENJNk1UY3lOek13TmpVNU5pd2laWGh3SWpveE56VTRPRFF5TlRrMkxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuQ2VYazhjVndqNURreV9Ubzd5Si1RSkhERVdGNjUyaTRYU1dISFBOcjZpOCIsInAiOjE0OTQyMjYwMSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzI3MzA2NTk2LCJleHAiOjE3Mjk4OTg1OTYsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.jpKlJPxtEELfZudk10Qcbs-CcWm9eSx6R2D8w40N1us?
