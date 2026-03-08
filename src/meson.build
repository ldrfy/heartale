pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'heartale'

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)
conf.set('APP_ID', APP_ID)

configure_file(
    input: 'heartale.in',
    output: 'heartale',
    configuration: conf,
    install: true,
    install_dir: get_option('bindir'),
    install_mode: 'rwxr-xr-x',
)

heartale_sources = [
    '__init__.py',
    'gui_app.py',
    'cli_reader.py',
    'main.py',
    'preferences.py',
    'window.py',
]

install_data(heartale_sources, install_dir: moduledir)

heartale_sources_pages = [
    'pages/__init__.py',
    'pages/reader_page.py',
    'pages/reader_session.py',
    'pages/reader_settings.py',
    'pages/reader_toc.py',
    'pages/shelf_page.py',
]

install_data(heartale_sources_pages, install_dir: moduledir / 'pages')


heartale_sources_entity = [
    'entity/__init__.py',
    'entity/book.py',
    'entity/time_read.py',
]

install_data(heartale_sources_entity, install_dir: moduledir / 'entity')


heartale_sources_widgets = [
    'widgets/__init__.py',
    'widgets/shelf_row.py',
    'widgets/pg_tag_view.py',
    'widgets/dialog_input.py',
    'widgets/properties_view.py',
]
install_data(heartale_sources_widgets, install_dir: moduledir / 'widgets')


heartale_sources_servers = [
    'servers/__init__.py',
    'servers/legado.py',
    'servers/txt.py',
]
install_data(heartale_sources_servers, install_dir: moduledir / 'servers')


tts_sources_servers = [
    'tts/__init__.py',
    'tts/read_runner.py',
    'tts/cache.py',
]
install_data(tts_sources_servers, install_dir: moduledir / 'tts')

tts_sources_backends = [
    'tts/backends/__init__.py',
    'tts/backends/android.py',
]
install_data(tts_sources_backends, install_dir: moduledir / 'tts' / 'backends')


heartale_sources_utils = [
    'utils/__init__.py',
    'utils/i18n.py',
    'utils/reader.py',
    'utils/debug.py',
    'utils/debug_gtk.py',
    'utils/gui.py',
    'utils/text.py',
    'utils/check_update.py',
]
install_data(heartale_sources_utils, install_dir: moduledir / 'utils')




subdir('res')
