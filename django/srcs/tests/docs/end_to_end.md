## test sales order with physical stock efficiancy
1. sales order list page create sales order, choose physical stock efficiancy
2. sales order detail page allocate only physical stock
3. inventory stock reservation page should have card for reserved by sales rep
4. sales order detail page confirm sales order, should have Button Release to Warehouse to create inventory movement
5. sales order detail page status change to processing
6. inventory stock movement should have movement by sales rep and can confirm to ship it
7. sales order detail page status change to completed

### bug found
-


## test sales order with physical and arriving stock efficiancy
1. stock controller create arriving stock without Purchase Order
2. sales order list page create sales order
3. sales order detail page allocate physical stock first and then arrive stock
4. inventory arrival detail page start receiving with expected quantity
5. reservation still stay old context, inventory movement auto create for arrival receiving
6. inventory movement completed, stock reservation created, arrival reservation is promoted, sales order allocate is promote to stock reservation
7. sales order reslease to warehouse, its status is processing
8. inventory stock movement completed, stock reservation is completed
9. sales order detail page status change to shipped


### need features
1. sale order item allocate page if arriving not show in the list cause date of arriving is more than order expected date should show details of arriving nearest date first but can not select the arriving until user has change order expected date more than arriving date **handled but not user end to end testing


### bug found
-

## test sales order with shortage
1. sale rep, create sale order with shortage item, the shortage item status is pending
2. stock controller, go to shortage lise then click pending tab to create PO from shortage selection
3. sale rep, order detail page the shortage item status is PO created
4. stock controller, go to the PO to confirm order
5. stock controller, create arriving stock from purchase order
6. sales rep, order detail page shortage should promote to arriving reservation and sale order status should pre-order
7. wh admin, start receiving arriving stock



### bug found

### need features
1. material shortages list should card UI same as sales order page
