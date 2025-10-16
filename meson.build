project(
    'heartale',
    version: '0.1.0',
    meson_version: '>= 1.0.0',
    default_options: [
        'warning_level=2',
        'werror=false',
    ],
)

i18n = import('i18n')
gnome = import('gnome')

APP_ID = 'cool.ldr.' + meson.project_name()
APP_DES = 'read.'

PACKAGE_URL = 'https://github.com/ldrfy/heartale'
PACKAGE_URL_BUG = 'https://github.com/ldrfy/heartale/issues'


subdir('data')
subdir('src')
subdir('po')
subdir('pkg')

gnome.post_install(
    glib_compile_schemas: true,
    gtk_update_icon_cache: true,
    update_desktop_database: true,
)