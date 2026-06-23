"""Live evaluation runners that POPULATE the eval-fabric stores.

The API surface (app.main) only READS reproduced-vs-claimed / frontier data. These runners are
what actually executes a live comparison and writes the rows the API then serves — closing the
loop from "we claim parity" to "we reproduced it, here is the evidence".
"""
