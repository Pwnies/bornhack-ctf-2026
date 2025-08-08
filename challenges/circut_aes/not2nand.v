(* techmap_celltype = "$_NOT_" *)
module not2nand(input A, output Y);
    \$_NAND_ g (
        .A(A), .B(A),
        .Y(Y)
    );
endmodule 
