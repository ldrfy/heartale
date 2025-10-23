deps = 'python3,python3-requests'
deps += ',python3-gi,libadwaita-1-0(>= 1.4)'


conf_pkg_deb = configuration_data()
foreach key : conf_pkg.keys()
    conf_pkg_deb.set(key, conf_pkg.get(key))
endforeach
conf_pkg_deb.set('DEPS', deps)

configure_file(
    input: 'control',
    output: 'control',
    configuration: conf_pkg_deb,
    install: false,
)