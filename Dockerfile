ARG BASE_IMAGE="python:3.13.0"

FROM ${BASE_IMAGE} AS base

ENV HOME_PATH="/opt"
ENV PATH="${HOME_PATH}/.venv/bin:${PATH}"

WORKDIR ${HOME_PATH}

FROM base AS deps

RUN pip install --no-cache-dir --upgrade pip \
&& pip install --no-cache-dir --upgrade uv==0.5.1

COPY pyproject.toml uv.lock ${HOME_PATH}/
RUN uv sync --frozen --no-install-project --no-dev

FROM deps AS development

COPY --from=deps ${HOME_PATH}/.venv ${HOME_PATH}/.venv
COPY app ${HOME_PATH}/app
WORKDIR ${HOME_PATH}

EXPOSE 8888

ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8888"]