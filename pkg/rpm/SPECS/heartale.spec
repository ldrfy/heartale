%define Name @APP_NAME@

Name: %{Name}
Version: @VERSION@
Release: 1
Summary: @APP_DES@
Summary(zh_CN): 看小说、听小说
License:  GPLv3+
URL:      @PACKAGE_URL@
Source0:  %{Name}-%{version}.zip
%global debug_package %{nil}
Requires: @DEPS@

%description
An easy and pleasant way to translate.
Support many translation services. Especially suitable for document translation.

%description -l zh_CN
看小说、听小说，支持 Legado 同步

%prep
%setup -q

%build
meson setup _build --prefix=/usr
meson compile -C _build


%check
meson test -C _build --print-errorlogs

%install
meson install -C _build --destdir=%{buildroot}


%files
/usr/bin/%{Name}
/usr/share
