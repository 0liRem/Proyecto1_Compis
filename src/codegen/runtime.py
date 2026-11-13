

DATOS = {
    "fatal": [
        ('__msg_div', 'Error de ejecucion: division entre cero\\n'),
        ('__msg_null', 'Error de ejecucion: acceso a objeto o arreglo nulo\\n'),
        ('__msg_bounds', 'Error de ejecucion: indice de arreglo fuera de rango\\n'),
    ],
    "print_bool": [('__s_true', 'true'), ('__s_false', 'false')],
    "print_str": [('__s_null', 'null')],
    "str_concat": [('__s_empty', '')],
}

CODIGO = {
    "fatal": """\
__rt_divzero:
    la $a0, __msg_div
    j __rt_fatal
__rt_null:
    la $a0, __msg_null
    j __rt_fatal
__rt_bounds:
    la $a0, __msg_bounds
__rt_fatal:
    li $v0, 4
    syscall
    li $v0, 10
    syscall
""",
    "print_bool": """\
__print_bool:                  # $a0 = 0/1 -> imprime true/false y salto de línea
    beqz $a0, __pb_false
    la $a0, __s_true
    j __pb_out
__pb_false:
    la $a0, __s_false
__pb_out:
    li $v0, 4
    syscall
    li $a0, 10
    li $v0, 11
    syscall
    jr $ra
""",
    "print_str": """\
__print_str:                   # $a0 = cadena (0 = null) -> imprime y salto de línea
    bnez $a0, __ps_ok
    la $a0, __s_null
__ps_ok:
    li $v0, 4
    syscall
    li $a0, 10
    li $v0, 11
    syscall
    jr $ra
""",
    "str_eq": """\
__str_eq:                      # $a0, $a1 cadenas -> $v0 = 1 si son iguales
    beq $a0, $a1, __se_yes
    beqz $a0, __se_no
    beqz $a1, __se_no
__se_loop:
    lb $t8, 0($a0)
    lb $t9, 0($a1)
    bne $t8, $t9, __se_no
    beqz $t8, __se_yes
    addiu $a0, $a0, 1
    addiu $a1, $a1, 1
    j __se_loop
__se_yes:
    li $v0, 1
    jr $ra
__se_no:
    li $v0, 0
    jr $ra
""",
    "str_concat": """\
__str_concat:                  # $a0 + $a1 -> $v0 = nueva cadena en el heap
    bnez $a0, __sc_a
    la $a0, __s_empty
__sc_a:
    bnez $a1, __sc_b
    la $a1, __s_empty
__sc_b:
    move $t8, $a0
    move $a2, $zero
__sc_l1:
    addu $t9, $t8, $a2
    lb $t9, 0($t9)
    beqz $t9, __sc_l2
    addiu $a2, $a2, 1
    j __sc_l1
__sc_l2:
    move $a3, $zero
__sc_l3:
    addu $t9, $a1, $a3
    lb $t9, 0($t9)
    beqz $t9, __sc_alloc
    addiu $a3, $a3, 1
    j __sc_l3
__sc_alloc:
    addu $a0, $a2, $a3
    addiu $a0, $a0, 1
    li $v0, 9
    syscall
    move $t9, $v0
__sc_c1:
    beqz $a2, __sc_c2
    lb $a0, 0($t8)
    sb $a0, 0($t9)
    addiu $t8, $t8, 1
    addiu $t9, $t9, 1
    addiu $a2, $a2, -1
    j __sc_c1
__sc_c2:
    lb $a0, 0($a1)
    sb $a0, 0($t9)
    beqz $a0, __sc_end
    addiu $a1, $a1, 1
    addiu $t9, $t9, 1
    j __sc_c2
__sc_end:
    jr $ra
""",
}
CODIGO["str_eq"] = CODIGO["str_eq"]
