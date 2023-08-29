# CoT_Collect

As part of a larger project that involved storing radio network metrics in a time series database, a version of this script was used to track location of ATAK devices as network strength of the radios transmitting their messages increased or decreased for later analysis.

This python script allows users (on Windows or Linux) to choose a network interface to montior for Cursor-on-Target (CoT) packets and presents them on an HTTP server to be scraped by Prometheus TSDB for storage.

The relevant portion of the Prometheus configuration will be added in the future.


