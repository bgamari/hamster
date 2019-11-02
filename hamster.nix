{ stdenv, fetchzip, pythonPackages, makeWrapper, wrapGAppsHook
, docbook2x, libxslt, gnome-doc-utils
, intltool, dbus-glib, glib, gobject-introspection, gtk3
, hicolor-icon-theme
, wafHook
}:

# TODO: Add optional dependency 'wnck', for "workspace tracking" support. Fixes
# this message:
#
#   WARNING:root:Could not import wnck - workspace tracking will be disabled

pythonPackages.buildPythonApplication rec {
  name = "hamster-time-tracker-1.04";

  src = ./.;

  nativeBuildInputs = [
    makeWrapper wafHook glib intltool wrapGAppsHook gnome-doc-utils docbook2x libxslt
  ];

  buildInputs = [
    dbus-glib hicolor-icon-theme
  ];

  propagatedBuildInputs = with pythonPackages; [
    gobject-introspection pygobject3 gtk3 glib pyxdg dbus-python
  ];

  wafConfigureFlags = [ ];

  preFixup = ''
    wrapPythonProgramsIn $out/lib/hamster-time-tracker "$out $propagatedBuildInputs"
    glib-compile-schemas $out/share/gsettings-schemas/hamster-time-tracker-1.04/glib-2.0/schemas
  '';
  postFixup = ''
    wrapProgram "$out/lib/hamster-time-tracker/hamster-service" \
      "''${gappsWrapperArgs[@]}"
    wrapProgram "$out/lib/hamster-time-tracker/hamster-windows-service" \
      "''${gappsWrapperArgs[@]}"
  '';

  # error: invalid command 'test'
  doCheck = false;

  meta = with stdenv.lib; {
    description = "Time tracking application";
    homepage = https://projecthamster.wordpress.com/;
    license = licenses.gpl3;
    platforms = platforms.all;
    maintainers = [ maintainers.bjornfor ];
  };
}

