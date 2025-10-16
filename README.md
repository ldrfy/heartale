# heartale

A description of this project.

```bash
wget https://raw.githubusercontent.com/flatpak/flatpak-builder-tools/refs/heads/master/pip/flatpak-pip-generator.py
mv flatpak-pip-generator.py ~/.local/bin/flatpak-pip-generator
chmod +x ~/.local/bin/flatpak-pip-generator


flatpak-pip-generator requests --yaml

flatpak-builder --user --install --force-clean build-dir cool.ldr.heartale.yaml
```
