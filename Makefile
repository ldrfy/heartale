TO_LANG=zh_CN
VERSION=0.1.0
DISK = ../../../dist/
BUILD_PKG=build/pkg
DESTDIR = "/"
PREFIX = "${HOME}/.local/"
# PREFIX = "${PWD}/test/"
BASE_URL = https://github.com/ldrfy/heartale/releases/download/auto

update-pot:
	xgettext -d "heartale" \
			--output=./po/heartale.pot \
			--copyright-holder="yuhldr" \
			--package-name="cool.ldr.heartale" \
			--msgid-bugs-address="yuhldr@gmail.com" \
			--add-comments=TRANSLATORS \
			--files-from=./po/POTFILES

clear:
	rm -rf build test
	mkdir -p dist
	rm -rf {HOME}/.local/share/glib-2.0/schemas/gschemas.compiled
	rm -rf {HOME}/.local/lib/heartale
	rm -rf /tmp/v${VERSION}.zip
	rm -rf /tmp/heartale-${VERSION}

test:clear
	meson setup build --prefix=${PREFIX}
	meson compile -C build
	meson test -C build
	# meson dist -C build --allow-dirty
	DESTDIR=${DESTDIR} meson install -C build

.PHONY: build other update-pot update-po po-init test whl rename
