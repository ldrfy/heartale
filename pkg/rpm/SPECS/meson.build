deps0 = 'python3 python3-requests'
deps = deps0 + ' python3-pillow python3-gobject libadwaita'


conf_pkg_rpm = configuration_data()
foreach key : conf_pkg.keys()
    conf_pkg_rpm.set(key, conf_pkg.get(key))
endforeach
conf_pkg_rpm.set('DEPS', deps)

configure_file(
    input: 'heartale.spec',
    output: 'heartale.spec',
    configuration: conf_pkg_rpm,
    install: false,
)


conf_pkg_rpm_suse = configuration_data()
foreach key : conf_pkg.keys()
    conf_pkg_rpm_suse.set(key, conf_pkg.get(key))
endforeach

deps = deps0 + ' python3-Pillow python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1'

conf_pkg_rpm_suse.set('DEPS', deps)

configure_file(
    input: 'heartale.spec',
    output: 'heartale-suse.spec',
    configuration: conf_pkg_rpm_suse,
    install: false,
)
