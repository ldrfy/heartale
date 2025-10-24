TO_LANG=zh_CN
VERSION=0.1.0
NAME=heartale
APP_ID=cool.ldr.${NAME}
PREFIX = "/usr/"
BASE_URL = https://github.com/ldrfy/${NAME}/releases/download/auto

update-pot:
	xgettext -d "${NAME}" \
			--output=./po/${NAME}.pot \
			--copyright-holder="yuhldr" \
			--package-name="${APP_ID}" \
			--msgid-bugs-address="yuhldr@gmail.com" \
			--add-comments=TRANSLATORS \
			--files-from=./po/POTFILES

clear:
	rm -rf build test
	mkdir -p dist
	mkdir -p build

build:
	meson setup build --prefix=${PREFIX}
	meson compile -C build
	meson test -C build
	# meson dist -C build --allow-dirty

install: build
	$(MAKE) build PREFIX=${HOME}/.local/
# 	安装位置与PREFIX不一致时使用DESTDIR
# 	DESTDIR=${HOME}/.local/ meson install -C build
	meson install -C build
	${NAME}

uninstall:
	rm -rf ${HOME}/.local/share/${NAME}
	rm -rf ${HOME}/.local/share/applications/${APP_ID}.desktop
	rm -rf ${HOME}/.local/share/dbus-1/services/${APP_ID}.service
	rm -rf ${HOME}/.local/share/metainfo/${APP_ID}.metainfo.xml
	rm -rf ${HOME}/.local/share/icons/hicolor/scalable/apps/${APP_ID}.svg
	rm -rf ${HOME}/.local/share/icons/hicolor/symbolic/apps/${APP_ID}-symbolic.svg
	rm -rf ${HOME}/.local/share/metainfo/${APP_ID}.metainfo.xml
	rm -rf ${HOME}/.local/share/glib-2.0/schemas/${APP_ID}.gschema.xml
	rm -rf ${HOME}/.local/share/glib-2.0/schemas/gschemas.compiled
	rm -rf ${HOME}/.local/lib/${NAME}
	rm -rf ${HOME}/.local/bin/${NAME}
	rm -rf /tmp/v${VERSION}.zip
	rm -rf /tmp/${NAME}-${VERSION}

PATH_ZIP = test/zip/${NAME}-${VERSION}/
build_zip:
	mkdir -p ${PATH_ZIP}
	cp -r data ${PATH_ZIP}
	cp -r pkg ${PATH_ZIP}
	cp -r po ${PATH_ZIP}
	cp -r src ${PATH_ZIP}
	cp -r meson.build ${PATH_ZIP}
	cp -r COPYING ${PATH_ZIP}
	cd ${PATH_ZIP}/../ && \
	zip -r ${NAME}-${VERSION}.zip ${NAME}-${VERSION}

PATH_AUR = build/pkg/aur/
pkg_aur_:
	cp ${PATH_ZIP}/../${NAME}-${VERSION}.zip ${PATH_AUR}

	cd build/pkg/aur/ && \
	makepkg -sf

	cp ${PATH_AUR}/${NAME}-${VERSION}-1-any.pkg.tar.zst dist/


pkg_aur: clear build build_zip pkg_aur_
# sudo pacman -U dist/${NAME}-${VERSION}-1-any.pkg.tar.zst


PATH_FLATPAK = build/pkg/flatpak/
pkg_flatpak_:
	mkdir -p ${PATH_FLATPAK}
	cp pkg/flatpak/* ${PATH_FLATPAK}
	cp ${PATH_ZIP}/../${NAME}-${VERSION}.zip ${PATH_FLATPAK}

	cd ${PATH_FLATPAK} && \
	unzip ${NAME}-${VERSION}.zip && \
	mv ${NAME}-${VERSION} ${NAME} && \
	flatpak-builder --repo=repo build-dir cool.ldr.heartale.yaml && \
	flatpak build-bundle repo cool.ldr.heartale.flatpak cool.ldr.heartale

	cp ${PATH_FLATPAK}/${APP_ID}.flatpak dist/${APP_ID}-${VERSION}.flatpak


pkg_flatpak: clear build build_zip pkg_flatpak_
# flatpak install --user dist/${APP_ID}-${VERSION}.flatpak



PATH_DEB = build/pkg/deb/

pkg_deb_:
	DESTDIR=../${PATH_DEB} meson install -C build

	cd "${PWD}/${PATH_DEB}/../" && \
	dpkg -b deb ./deb/${NAME}-${VERSION}-x86_64.deb

	cp ${PATH_DEB}/${NAME}-${VERSION}-x86_64.deb dist/

pkg_deb: clear build pkg_deb_


PATH_RPM = build/pkg/rpm/
pkg_rpm_:

	mkdir -p ${PWD}/${PATH_RPM}/SOURCES/${NAME}-${VERSION} && \
	cp ${PATH_ZIP}/../${NAME}-${VERSION}.zip ${PATH_RPM}/SOURCES/

	rpmbuild -bb ${PWD}/${PATH_RPM}/SPECS/${NAME}.spec \
		--define "_topdir ${PWD}/${PATH_RPM}/"

	cp ${PATH_RPM}/RPMS/x86_64/${NAME}-${VERSION}-1.x86_64.rpm dist/${NAME}-${VERSION}-1.x86_64.rpm

	rpmbuild -bb ${PWD}/${PATH_RPM}/SPECS/${NAME}-suse.spec \
		--define "_topdir ${PWD}/${PATH_RPM}/"

	cp ${PATH_RPM}/RPMS/x86_64/${NAME}-${VERSION}-1.x86_64.rpm dist/${NAME}-${VERSION}-1.x86_64-suse.rpm

pkg_rpm: clear build build_zip pkg_rpm_


pkg_all: clear build build_zip pkg_aur_ pkg_deb_ pkg_rpm_ pkg_flatpak_
	cp dist/* ${HOME}/data/my/vmware/files



.PHONY: build build_zip update-pot test install uninstall
