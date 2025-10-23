deps = '"python-requests"'
build_deps = '"meson" "libadwaita" "python-gobject"'


conf_pkg_aur = configuration_data()
foreach key : conf_pkg.keys()
    conf_pkg_aur.set(key, conf_pkg.get(key))
endforeach
conf_pkg_aur.set('DEPS', deps)
conf_pkg_aur.set('BUILD_DEPS', build_deps)

configure_file(
    input: 'PKGBUILD',
    output: 'PKGBUILD',
    configuration: conf_pkg_aur,
    install: false,
)
