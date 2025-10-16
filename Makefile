TO_LANG=zh_CN
VERSION=0.1.0
NAME=heartale
APP_ID=cool.ldr.${NAME}
DISK = ../../../dist/
BUILD_PKG=build/pkg
DESTDIR = "/"
PREFIX = "${HOME}/.local/"
# PREFIX = "${PWD}/test/"
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
	rm -rf ${PREFIX}/share/${NAME}
	rm -rf ${PREFIX}/share/applications/${APP_ID}.desktop
	rm -rf ${PREFIX}/share/dbus-1/services/${APP_ID}.service
	rm -rf ${PREFIX}/share/metainfo/${APP_ID}.metainfo.xml
	rm -rf ${PREFIX}/share/icons/hicolor/scalable/apps/${APP_ID}.svg
	rm -rf ${PREFIX}/share/icons/hicolor/symbolic/apps/${APP_ID}-symbolic.svg
	rm -rf ${PREFIX}/share/metainfo/${APP_ID}.metainfo.xml
	rm -rf ${PREFIX}/share/glib-2.0/schemas/${APP_ID}.gschema.xml
	rm -rf {HOME}/.local/share/glib-2.0/schemas/gschemas.compiled
	rm -rf {HOME}/.local/lib/${NAME}
	rm -rf /tmp/v${VERSION}.zip
	rm -rf /tmp/${NAME}-${VERSION}

test:clear
	meson setup build --prefix=${PREFIX}
	meson compile -C build
	meson test -C build
	# meson dist -C build --allow-dirty
	DESTDIR=${DESTDIR} meson install -C build
	${NAME}

.PHONY: build other update-pot update-po po-init test whl rename
