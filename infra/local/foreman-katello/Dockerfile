FROM --platform=linux/amd64 fedora:40

# Trim unnecessary systemd targets so the container starts cleanly
ENV container=docker
RUN systemctl mask \
        dev-hugepages.mount \
        sys-fs-fuse-connections.mount \
        systemd-update-utmp.service \
        systemd-tmpfiles-setup.service \
        getty.target \
        console-getty.service && \
    rm -f /etc/systemd/system/multi-user.target.wants/systemd-logind.service

# Foreman 3.11 + Katello 4.13 release repositories
RUN dnf -y install dnf-plugins-core && \
    dnf -y install \
        https://yum.theforeman.org/releases/3.11/f40/x86_64/foreman-release.rpm \
        https://yum.theforeman.org/katello/4.13/katello/f40/x86_64/katello-repos-latest.rpm \
        https://yum.puppet.com/puppet8-release-fedora-40.noarch.rpm && \
    dnf clean all

# Install foreman-installer (pulls katello scenario and all Pulp/Candlepin deps)
RUN dnf -y install foreman-installer && dnf clean all

# hammer CLI for post-install automation
RUN dnf -y install rubygem-hammer_cli_foreman rubygem-hammer_cli_katello && \
    dnf clean all

COPY bootstrap.sh /usr/local/bin/bootstrap.sh
RUN chmod +x /usr/local/bin/bootstrap.sh

# One-shot systemd service that runs the installer on first boot
COPY foreman-installer-bootstrap.service /etc/systemd/system/foreman-installer-bootstrap.service
RUN systemctl enable foreman-installer-bootstrap.service

VOLUME ["/var/lib/foreman", "/var/lib/pulp", "/etc/puppet"]

EXPOSE 443 80 24816

CMD ["/usr/sbin/init"]
