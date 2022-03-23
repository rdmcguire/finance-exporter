FROM image.libretechconsulting.com/library/python:3
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt
ENV CONFIG '/usr/src/app/finance-exporter.yaml'
ENV OPTS ''
COPY schema.yaml ./
COPY includes ./includes
COPY finance-exporter.py ./
CMD ["sh", "-c", "python3 finance-exporter.py -f ${CONFIG} ${OPTS}"]
