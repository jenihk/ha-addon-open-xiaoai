# 直接复用应用仓库预构建的多架构镜像（amd64 + arm64），
# 不在 HA 设备上编译 Rust 扩展，安装即用。
# 前置：open-xiaoai-ha-gateway 仓库的 GitHub Actions 已推送该镜像。
FROM ghcr.io/jenihk/open-xiaoai-ha-gateway:latest

ARG BUILD_VERSION

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="aarch64|amd64"

COPY run.sh /run.sh
COPY generate_config.py /generate_config.py
COPY download_models.sh /download_models.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
